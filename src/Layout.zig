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
    pub const S = struct {
        x: f32,
        y: f32,
        z: f32,
        w: f32,
    };
    comptime {
        std.testing.expectEqual(16, @sizeOf(S)) catch unreachable;
    }
    pub const SoA = struct {
        x: []f32,
        y: []f32,
        z: []f32,
        w: []f32,
    };

    pub fn setup_aos(gen: *Gen, alloc: Allocator) !ArgTypes(run_aos) {
        const items = try alloc.alloc(S, gen.amount);
        for (items) |*s| {
            s.* = .{
                .x = gen.rand.float(f32),
                .y = gen.rand.float(f32),
                .z = gen.rand.float(f32),
                .w = gen.rand.float(f32),
            };
        }
        return .{items};
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

    pub fn run_aos(items: []S) f32 {
        var ret: f32 = 0.0;
        for (items) |p| {
            ret += compute(p.x, p.y, p.z, p.w);
        }
        return ret;
    }
    pub fn run_soa(items: SoA) f32 {
        var ret: f32 = 0.0;
        for (items.x, items.y, items.z, items.w) |x, y, z, w| {
            ret += compute(x, y, z, w);
        }
        return ret;
    }

    inline fn compute(a: f32, b: f32, c: f32, d: f32) f32 {
        // arbitrary time consuming computation
        return std.math.acos(a) * b / 2 * c + std.math.atan(d) * std.math.exp2(d);
    }
};

pub const AccessSomeFields = struct {
    pub const S = struct {
        x: f32,
        y: f32,
        z: f32,
        w: f32,
    };
    comptime {
        std.testing.expectEqual(16, @sizeOf(S)) catch unreachable;
    }
    pub const SoA = struct {
        x: []f32,
        y: []f32,
        z: []f32,
        w: []f32,
    };

    pub fn setup_aos(gen: *Gen, alloc: Allocator) !ArgTypes(run_aos) {
        const items = try alloc.alloc(S, gen.amount);
        for (items) |*s| {
            s.* = .{
                .x = gen.rand.float(f32),
                .y = gen.rand.float(f32),
                .z = gen.rand.float(f32),
                .w = gen.rand.float(f32),
            };
        }
        return .{items};
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

    pub fn run_aos(items: []S) f32 {
        var ret: f32 = 0.0;
        for (items) |s| {
            ret += compute(s.x, s.y, s.x, s.y);
        }
        return ret;
    }
    pub fn run_soa(items: SoA) f32 {
        var ret: f32 = 0.0;
        for (items.x, items.y, items.z, items.w) |x, y, z, w| {
            ret += compute(x, y, z, w);
        }
        return ret;
    }

    inline fn compute(a: f32, b: f32, c: f32, d: f32) f32 {
        // arbitrary time consuming computation
        return std.math.acos(a) * b / 2 * c + std.math.atan(d) * std.math.exp2(d);
    }
};

pub const AccessAllPaddedFields = struct {
    pub const S = struct {
        base: u32,
        div: u8,
        factor: u64,
    };
    comptime {
        std.testing.expectEqual(16, @sizeOf(S)) catch unreachable;
    }
    pub const SoA = struct {
        base: []u32,
        div: []u8,
        factor: []u64,
    };

    pub fn setup_aos(gen: *Gen, alloc: Allocator) !ArgTypes(run_aos) {
        const items = try alloc.alloc(S, gen.amount);
        for (items) |*s| {
            s.* = .{
                .base = gen.rand.int(u32),
                .div = gen.rand.intRangeLessThanBiased(u8, 2, 200),
                .factor = gen.rand.int(u64),
            };
        }
        return .{items};
    }
    pub fn setup_soa(gen: *Gen, alloc: Allocator) !ArgTypes(run_soa) {
        const bases = try alloc.alloc(u32, gen.amount);
        const divs = try alloc.alloc(u8, gen.amount);
        const factors = try alloc.alloc(u64, gen.amount);
        for (bases, divs, factors) |*base, *div, *factor| {
            base.* = gen.rand.int(u32);
            div.* = gen.rand.intRangeLessThanBiased(u8, 2, 200);
            factor.* = gen.rand.int(u64);
        }
        return .{.{ .base = bases, .div = divs, .factor = factors }};
    }

    pub fn run_aos(items: []S) u64 {
        var ret: u64 = 0.0;
        for (items) |p| {
            ret +%= compute(p.base, p.div, p.factor);
        }
        return ret;
    }
    pub fn run_soa(items: SoA) u64 {
        var ret: u64 = 0.0;
        for (items.base, items.div, items.factor) |base, div, factor| {
            ret +%= compute(base, div, factor);
        }
        return ret;
    }

    inline fn compute(base: u32, div: u8, factor: u64) u64 {
        // arbitrary time consuming computation
        return @as(u64, @intCast(base)) *% factor / @as(u64, @intCast(div));
    }
};

pub const WriteToOneField = struct {
    pub const S = struct {
        total: f32,
        x: f32,
        y: f32,
        z: f32,
    };
    comptime {
        std.testing.expectEqual(16, @sizeOf(S)) catch unreachable;
    }
    pub const SoA = struct {
        total: []f32,
        x: []f32,
        y: []f32,
        z: []f32,
    };

    pub fn setup_aos(gen: *Gen, alloc: Allocator) !ArgTypes(run_aos) {
        const items = try alloc.alloc(S, gen.amount);
        for (items) |*s| {
            s.* = .{
                .total = 0.0,
                .x = gen.rand.float(f32),
                .y = gen.rand.float(f32),
                .z = gen.rand.float(f32),
            };
        }
        return .{items};
    }
    pub fn setup_soa(gen: *Gen, alloc: Allocator) !ArgTypes(run_soa) {
        const items: SoA = .{
            .total = try alloc.alloc(f32, gen.amount),
            .x = try alloc.alloc(f32, gen.amount),
            .y = try alloc.alloc(f32, gen.amount),
            .z = try alloc.alloc(f32, gen.amount),
        };
        for (items.total, items.x, items.y, items.z) |*total, *x, *y, *z| {
            total.* = 0.0;
            x.* = gen.rand.float(f32);
            y.* = gen.rand.float(f32);
            z.* = gen.rand.float(f32);
        }
        return .{items};
    }

    pub fn run_aos(items: []S) f32 {
        var ret: f32 = 0.0;
        for (items) |*p| {
            p.total = compute(p.x, p.y, p.z);
            ret += p.total;
        }
        return ret;
    }
    pub fn run_soa(items: SoA) f32 {
        var ret: f32 = 0.0;
        for (items.total, items.x, items.y, items.z) |*total, x, y, z| {
            total.* = compute(x, y, z);
            ret += total.*;
        }
        return ret;
    }

    inline fn compute(x: f32, y: f32, z: f32) f32 {
        // arbitrary time consuming computation
        return x * 100 / (y + 0.1) * z;
    }
};
