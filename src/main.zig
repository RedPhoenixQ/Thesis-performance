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
        // Layout tests
        inline for (.{
            .{ "access-all-fields", Layout.AccessAllFields },
        }) |opts| {
            defer std.debug.assert(arena_instance.reset(.retain_capacity));
            const name, const Test = opts;

            const samples_aos, const returns_aos = try measure.run(
                arena,
                iterations,
                Test.run_aos,
                Test.setup_aos,
                @constCast(&Layout.Gen.init(seed, size)),
            );
            const file_aos = try dir.createFile(
                try std.fmt.bufPrint(
                    &buf,
                    "{s}-aos-{d}-{d}.csv",
                    .{ name, size, std.fmt.fmtIntSizeBin(@sizeOf(Layout.AccessAllFields.S) * size) },
                ),
                .{ .mode = 0o666 },
            );
            try measure.writeToCSV(samples_aos, file_aos.writer().any());
            file_aos.close();

            const samples_soa, const returns_soa = try measure.run(
                arena,
                iterations,
                Test.run_soa,
                Test.setup_soa,
                @constCast(&Layout.Gen.init(seed, size)),
            );
            const file_soa = try dir.createFile(
                try std.fmt.bufPrint(
                    &buf,
                    "{s}-soa-{d}-{d}.csv",
                    .{ name, size, std.fmt.fmtIntSizeBin(@sizeOf(Layout.AccessAllFields.S) * size) },
                ),
                .{ .mode = 0o666 },
            );
            try measure.writeToCSV(samples_soa, file_soa.writer().any());
            file_soa.close();

            std.testing.expectEqualDeep(returns_aos, returns_soa) catch unreachable;
        }
    }
}

test {
    std.testing.refAllDeclsRecursive(@This());
}
