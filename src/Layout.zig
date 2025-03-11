const std = @import("std");
const Allocator = std.mem.Allocator;
const ArgTypes = @import("common.zig").ArgTypes;

pub const Gen = struct {
    rand: std.Random,
    amount: usize,

    pub fn init(seed: u64, amount: usize) @This() {
        return .{
            .rand = @constCast(&std.Random.DefaultPrng.init(seed)).random(),
            .amount = amount,
        };
    }
};

pub const AccessAllFields = struct {
    const S = struct {
        x: f32,
        y: f32,
        z: f32,
        w: f32,
    };
    const SoA = struct {
        x: []f32,
        y: []f32,
        z: []f32,
        w: []f32,
    };

    pub fn setup_aos(gen: *Gen, alloc: Allocator) !ArgTypes(run_aos) {
        const points = try alloc.alloc(S, gen.amount);
        for (points) |*p| {
            p.* = .{
                .x = gen.rand.float(f32),
                .y = gen.rand.float(f32),
                .z = gen.rand.float(f32),
                .w = gen.rand.float(f32),
            };
        }
        return .{points};
    }
    pub fn setup_soa(gen: *Gen, alloc: Allocator) !ArgTypes(run_soa) {
        const xs = try alloc.alloc(f32, gen.amount);
        const ys = try alloc.alloc(f32, gen.amount);
        const zs = try alloc.alloc(f32, gen.amount);
        const ws = try alloc.alloc(f32, gen.amount);
        for (xs, ys, zs, ws) |*x, *y, *z, *w| {
            x.* = gen.rand.float(f32);
            y.* = gen.rand.float(f32);
            z.* = gen.rand.float(f32);
            w.* = gen.rand.float(f32);
        }
        return .{.{ .x = xs, .y = ys, .z = zs, .w = ws }};
    }

    pub fn run_aos(points: []S) f32 {
        var ret: f32 = 0.0;
        for (points) |p| {
            ret += compute(p.x, p.y, p.z, p.w);
        }
        return ret;
    }
    pub fn run_soa(points: SoA) f32 {
        var ret: f32 = 0.0;
        for (points.x, points.y, points.z, points.w) |x, y, z, w| {
            ret += compute(x, y, z, w);
        }
        return ret;
    }

    inline fn compute(a: f32, b: f32, c: f32, d: f32) f32 {
        // arbitrary time consuming computation
        return std.math.acos(a) * b / 2 * c + std.math.atan(d) * std.math.exp2(d);
    }
};
