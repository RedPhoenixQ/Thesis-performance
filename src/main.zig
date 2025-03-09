const std = @import("std");
const native_endian = @import("builtin").cpu.arch.endian();

const measure = @import("measure.zig");
const ArgTypes = @import("common.zig").ArgTypes;

pub fn main() !void {
    const stdout_file = std.io.getStdOut().writer();
    var bw = std.io.bufferedWriter(stdout_file);
    const stdout = bw.writer().any();

    const TestMeasure = struct {
        rand: std.Random.Pcg,
        fn init() @This() {
            return .{ .rand = std.Random.Pcg.init(123) };
        }
        fn run(int: u32) u32 {
            std.debug.print("hahahahah {d}\n", .{int});
            return int;
        }
        fn next(self: *@This(), alloc: std.mem.Allocator) ArgTypes(run) {
            _ = alloc;
            return .{self.rand.random().int(u32)};
        }
    };

    const samples, const returns = try measure.run(std.heap.page_allocator, 10, TestMeasure.run, TestMeasure.next, @constCast(&TestMeasure.init()));

    std.debug.print("Hash: {any}\n", .{returns});

    try measure.writeToCSV(samples, stdout);
    try bw.flush();
}

test {
    std.testing.refAllDeclsRecursive(@This());
}
