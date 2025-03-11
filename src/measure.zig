const std = @import("std");
const PERF = std.os.linux.PERF;
const fd_t = std.posix.fd_t;

const ReturnType = @import("common.zig").ReturnType;

const Sample = struct {
    wall_clock: u64,
    cpu_cycles: u64,
    instructions: u64,
    cache_references: u64,
    cache_misses: u64,
    branch_misses: u64,
};

const PerfMeasurement = struct {
    name: []const u8,
    config: u32,
};

const perf_counters = [_]PerfMeasurement{
    .{ .name = "cpu_cycles", .config = @intFromEnum(PERF.COUNT.HW.CPU_CYCLES) },
    .{ .name = "instructions", .config = @intFromEnum(PERF.COUNT.HW.INSTRUCTIONS) },
    .{ .name = "cache_references", .config = @intFromEnum(PERF.COUNT.HW.CACHE_REFERENCES) },
    .{ .name = "cache_misses", .config = @intFromEnum(PERF.COUNT.HW.CACHE_MISSES) },
    .{ .name = "branch_misses", .config = @intFromEnum(PERF.COUNT.HW.BRANCH_MISSES) },
};

pub fn run(alloc: std.mem.Allocator, iterations: u32, comptime func: anytype, comptime setup_func: anytype, setup_ctx: anytype) !struct {
    []Sample,
    /// hash of all return values
    []ReturnType(func),
} {
    var timer = try std.time.Timer.start();
    var fds: [perf_counters.len]fd_t = @splat(-1);

    // Create counters
    for (perf_counters, &fds) |perf, *fd| {
        var attr: std.posix.system.perf_event_attr = .{
            .type = PERF.TYPE.HARDWARE,
            .config = perf.config,
            .flags = .{
                .disabled = true,
                .exclude_kernel = true,
                .exclude_hv = true,
                .enable_on_exec = true,
            },
        };
        fd.* = std.posix.perf_event_open(&attr, 0, -1, fds[0], PERF.FLAG.FD_CLOEXEC) catch |err| {
            std.debug.panic("could not open perf event, {s}\n", .{@errorName(err)});
        };
    }

    const samples = try alloc.alloc(Sample, iterations);
    const returns = try alloc.alloc(ReturnType(func), iterations);

    var arena_instance = std.heap.ArenaAllocator.init(alloc);
    defer arena_instance.deinit();
    const arena = arena_instance.allocator();

    for (samples, returns) |*sample, *ret| {
        // Setup
        const args = try @call(.never_inline, setup_func, .{ setup_ctx, arena });

        // Start counting
        _ = std.os.linux.ioctl(fds[0], PERF.EVENT_IOC.RESET, PERF.IOC_FLAG_GROUP);
        timer.reset();
        _ = std.os.linux.ioctl(fds[0], PERF.EVENT_IOC.ENABLE, PERF.IOC_FLAG_GROUP);

        // Run computation
        ret.* = @call(.never_inline, func, args);
        std.mem.doNotOptimizeAway(ret.*);

        // Stop counting
        _ = std.os.linux.ioctl(fds[0], PERF.EVENT_IOC.DISABLE, PERF.IOC_FLAG_GROUP);
        sample.*.wall_clock = timer.read();

        // Collect counters
        inline for (0.., perf_counters) |i, counter| {
            @field(sample.*, counter.name) = readPerfFd(fds[i]);
        }

        // Reset
        const reset_success = arena_instance.reset(.retain_capacity);
        std.debug.assert(reset_success);
    }

    // Close counters
    for (fds) |fd| {
        const ret = std.os.linux.close(fd);
        std.debug.assert(ret != -1);
    }

    return .{ samples, returns };
}

// MIT license from https://github.com/andrewrk/poop/blob/e283827410e2caf751ce8f38d2ff5c217e1ce4cd/src/main.zig#L407
fn readPerfFd(fd: fd_t) usize {
    var result: usize = 0;
    const n = std.posix.read(fd, std.mem.asBytes(&result)) catch |err| {
        std.debug.panic("unable to read perf fd: {s}\n", .{@errorName(err)});
    };
    std.debug.assert(n == @sizeOf(usize));
    return result;
}

pub fn writeToCSV(samples: []Sample, writer: std.io.AnyWriter) !void {
    const sample_fields = @typeInfo(Sample).@"struct".fields;
    inline for (1.., sample_fields) |i, field| {
        try writer.writeAll(field.name);
        if (i < sample_fields.len) {
            try writer.writeByte(',');
        }
    }
    try writer.writeByte('\n');

    for (samples) |sample| {
        inline for (1.., sample_fields) |i, field| {
            try writer.print("{d}", .{@field(sample, field.name)});
            if (i < sample_fields.len) {
                try writer.writeByte(',');
            }
        }
        try writer.writeByte('\n');
    }
}

test {
    std.testing.refAllDeclsRecursive(@This());
}

test "measure printing" {
    const TestMeasure = struct {
        rand: std.Random.Pcg,
        fn init() @This() {
            return .{ .rand = std.Random.Pcg.init(123) };
        }
        fn work(int: u32) u32 {
            std.debug.print("testing {d}\n", .{int});
            return int;
        }
        fn next(self: *@This(), alloc: std.mem.Allocator) !@import("common.zig").ArgTypes(work) {
            _ = alloc;
            return .{self.rand.random().int(u32)};
        }
    };

    const iterations = 10;

    const samples, const returns = try run(std.heap.page_allocator, iterations, TestMeasure.work, TestMeasure.next, @constCast(&TestMeasure.init()));

    try std.testing.expectEqual(iterations, samples.len);
    try std.testing.expectEqual(iterations, returns.len);

    try std.testing.expectEqualSlices(u32, &.{ 3905061867, 754126603, 4065762767, 2021074206, 3493466093, 894905616, 960286935, 3164605636, 3720063109, 1153359134 }, returns);
}
