const std = @import("std");
const native_endian = @import("builtin").cpu.arch.endian();

const measure = @import("measure.zig");
const ArgTypes = @import("common.zig").ArgTypes;

const Layout = @import("Layout.zig");

pub fn main() !void {
    var arena_instance = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    const arena = arena_instance.allocator();

    const cwd = std.fs.cwd();
    const now = std.time.timestamp();

    var buf: [2048]u8 = undefined;

    // TODO: Make these input arguments
    const out_dir = "./output";
    const iterations = 30;
    var seed: u64 = @intCast(100);

    var dir = try cwd.makeOpenPath(try std.fmt.bufPrint(&buf, "{s}/{d}-{d}", .{ out_dir, now, seed }), .{});
    defer dir.close();

    var size: usize = 1 << 3;
    while (size < 1024 * 1024 * 2) : (size <<= 1) {
        seed += 1;
        {
            defer std.debug.assert(arena_instance.reset(.retain_capacity));
            const samples, _ = try measure.run(
                arena,
                iterations,
                Layout.AccessAllFields.run_aos,
                Layout.AccessAllFields.setup_aos,
                @constCast(&Layout.Gen.init(seed, size)),
            );
            const file = try dir.createFile(
                try std.fmt.bufPrint(
                    &buf,
                    "access-all-fields-aos-{d}-{d}.csv",
                    .{ size, std.fmt.fmtIntSizeBin(@sizeOf(Layout.AccessAllFields.S) * size) },
                ),
                .{ .mode = 0o666 },
            );
            defer file.close();
            try measure.writeToCSV(samples, file.writer().any());
        }
        {
            defer std.debug.assert(arena_instance.reset(.retain_capacity));
            const samples, _ = try measure.run(
                arena,
                iterations,
                Layout.AccessAllFields.run_soa,
                Layout.AccessAllFields.setup_soa,
                @constCast(&Layout.Gen.init(seed, size)),
            );
            const file = try dir.createFile(
                try std.fmt.bufPrint(
                    &buf,
                    "access-all-fields-soa-{d}-{d}.csv",
                    .{ size, std.fmt.fmtIntSizeBin(@sizeOf(f32) * 4 * size) },
                ),
                .{ .mode = 0o666 },
            );
            defer file.close();
            try measure.writeToCSV(samples, file.writer().any());
        }
    }
}

test {
    std.testing.refAllDeclsRecursive(@This());
}
