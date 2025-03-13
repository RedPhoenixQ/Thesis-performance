const std = @import("std");
const Allocator = std.mem.Allocator;
const ArgTypes = @import("common.zig").ArgTypes;

pub const Gen = struct {
    rand: std.Random,
    amount: usize,
    should_sort: bool,

    const Sort = enum {
        sorted,
        unsorted,
    };

    pub fn init(seed: u64, amount: usize, sort: Sort) @This() {
        return .{
            .rand = @constCast(&std.Random.DefaultPrng.init(seed)).random(),
            .amount = amount,
            .should_sort = sort == .sorted,
        };
    }
};

const Types = struct {
    const Tag = enum(u2) {
        a,
        b,
        c,

        fn T(self: @This()) type {
            return switch (self) {
                .a => A,
                .b => B,
                .c => C,
            };
        }
    };

    const A = struct {
        x: f32,
        y: f32,
        z: f32,
        velocities: struct {
            x: f32,
            y: f32,
            z: f32,
        },

        const Self = @This();

        const vtable: DynamicDispatch.Dyn.VTable = .{
            .update = dyn_update,
            .run = dyn_run,
        };
        fn dyn_update(ctx: *anyopaque) void {
            return update(@ptrCast(@alignCast(ctx)));
        }
        fn dyn_run(ctx: *anyopaque) f32 {
            return run(@ptrCast(@alignCast(ctx)));
        }

        fn gen(rand: std.Random) Self {
            return .{
                .x = (rand.float(f32) - 0.5) * 100,
                .y = (rand.float(f32) - 0.5) * 100,
                .z = (rand.float(f32) - 0.5) * 100,
                .velocities = .{
                    .x = (rand.float(f32) - 0.5) * 5,
                    .y = (rand.float(f32) - 0.5) * 5,
                    .z = (rand.float(f32) - 0.5) * 5,
                },
            };
        }

        fn update(self: *Self) void {
            self.x += self.velocities.x;
            self.y += self.velocities.y;
            self.z += self.velocities.z;
        }

        fn run(self: *Self) f32 {
            return self.x * 1000 + self.y * 100 + self.z * 10;
        }
    };

    const B = struct {
        x: f32,
        y: f32,
        velocities: struct {
            x: f32,
            y: f32,
        },

        const Self = @This();

        const vtable: DynamicDispatch.Dyn.VTable = .{
            .update = dyn_update,
            .run = dyn_run,
        };
        fn dyn_update(ctx: *anyopaque) void {
            return update(@ptrCast(@alignCast(ctx)));
        }
        fn dyn_run(ctx: *anyopaque) f32 {
            return run(@ptrCast(@alignCast(ctx)));
        }

        fn gen(rand: std.Random) Self {
            return .{
                .x = (rand.float(f32) - 0.5) * 100,
                .y = (rand.float(f32) - 0.5) * 100,
                .velocities = .{
                    .x = (rand.float(f32) - 0.5) * 5,
                    .y = (rand.float(f32) - 0.5) * 5,
                },
            };
        }

        fn update(self: *Self) void {
            self.x += self.velocities.x;
            self.y += self.velocities.y;
        }

        fn run(self: *Self) f32 {
            return self.x * 100 + self.y * 10;
        }
    };

    const C = struct {
        x: f64,
        y: f64,
        z: f64,
        velocities: struct {
            x: f64,
            y: f64,
            z: f64,
        },

        const Self = @This();

        const vtable: DynamicDispatch.Dyn.VTable = .{
            .update = dyn_update,
            .run = dyn_run,
        };
        fn dyn_update(ctx: *anyopaque) void {
            return update(@ptrCast(@alignCast(ctx)));
        }
        fn dyn_run(ctx: *anyopaque) f32 {
            return run(@ptrCast(@alignCast(ctx)));
        }

        fn gen(rand: std.Random) Self {
            return .{
                .x = (rand.float(f64) - 0.5) * 100,
                .y = (rand.float(f64) - 0.5) * 100,
                .z = (rand.float(f64) - 0.5) * 100,
                .velocities = .{
                    .x = (rand.float(f64) - 0.5) * 5,
                    .y = (rand.float(f64) - 0.5) * 5,
                    .z = (rand.float(f64) - 0.5) * 5,
                },
            };
        }

        fn update(self: *Self) void {
            self.x += self.velocities.x;
            self.y += self.velocities.y;
        }

        fn run(self: *Self) f32 {
            return @floatCast(self.x * 1000 + self.y * 100 + self.z * 10);
        }
    };
};

pub const DynamicDispatch = struct {
    const Dyn = struct {
        ptr: *anyopaque,
        vtable: *const VTable,

        const VTable = struct {
            update: *const fn (*anyopaque) void,
            run: *const fn (*anyopaque) f32,
        };

        const SorterContext = struct {
            items: []Dyn,
            pub fn lessThan(ctx: @This(), a: usize, b: usize) bool {
                return @intFromPtr(ctx.items[a].vtable) > @intFromPtr(ctx.items[b].vtable);
            }
            pub fn swap(ctx: @This(), a: usize, b: usize) void {
                return std.mem.swap(Dyn, &ctx.items[a], &ctx.items[b]);
            }
        };
    };

    pub fn setup(gen: *Gen, alloc: Allocator) !ArgTypes(run) {
        const items = try alloc.alloc(Dyn, gen.amount);
        for (items) |*s| {
            switch (gen.rand.enumValue(Types.Tag)) {
                inline else => |t| {
                    const T = t.T();
                    const v = try alloc.create(T);
                    v.* = T.gen(gen.rand);
                    s.* = .{
                        .ptr = v,
                        .vtable = &T.vtable,
                    };
                },
            }
        }
        if (gen.should_sort) {
            // This does not consider the order of the allocations.
            // Iterating over the sorted array will access the items non-linearly in memory,
            // potentially causing more cache misses
            std.mem.sortUnstableContext(0, items.len, Dyn.SorterContext{ .items = items });
        }
        return .{items};
    }

    pub fn run(items: []Dyn) f32 {
        var ret: f32 = 0.0;
        for (items) |s| {
            s.vtable.update(s.ptr);
            ret += s.vtable.run(s.ptr);
        }
        return ret;
    }
};

pub const TaggedDispatch = struct {
    const E = union(Types.Tag) {
        a: Types.A,
        b: Types.B,
        c: Types.C,

        const SorterContext = struct {
            items: []E,
            pub fn lessThan(ctx: @This(), a: usize, b: usize) bool {
                return @intFromEnum(ctx.items[a]) > @intFromEnum(ctx.items[b]);
            }
            pub fn swap(ctx: @This(), a: usize, b: usize) void {
                return std.mem.swap(E, &ctx.items[a], &ctx.items[b]);
            }
        };
    };

    pub fn setup(gen: *Gen, alloc: Allocator) !ArgTypes(run) {
        const items = try alloc.alloc(E, gen.amount);
        for (items) |*s| {
            s.* = switch (gen.rand.enumValue(Types.Tag)) {
                .a => E{ .a = .gen(gen.rand) },
                .b => E{ .b = .gen(gen.rand) },
                .c => E{ .c = .gen(gen.rand) },
            };
        }
        if (gen.should_sort) {
            std.mem.sortUnstableContext(0, items.len, E.SorterContext{ .items = items });
        }
        return .{items};
    }

    pub fn run(items: []E) f32 {
        var ret: f32 = 0.0;
        for (items) |*e| {
            ret += switch (e.*) {
                inline else => |*s| blk: {
                    s.update();
                    break :blk s.run();
                },
            };
        }
        return ret;
    }
};

pub const ExistentialProcessing = struct {
    const S = struct {
        a: []Types.A,
        b: []Types.B,
        c: []Types.C,
    };

    pub fn setup(gen: *Gen, alloc: Allocator) !ArgTypes(run) {
        var as = try std.ArrayListUnmanaged(Types.A).initCapacity(alloc, gen.amount);
        var bs = try std.ArrayListUnmanaged(Types.B).initCapacity(alloc, gen.amount);
        var cs = try std.ArrayListUnmanaged(Types.C).initCapacity(alloc, gen.amount);
        for (0..gen.amount) |_| {
            switch (gen.rand.enumValue(Types.Tag)) {
                .a => as.addOneAssumeCapacity().* = .gen(gen.rand),
                .b => bs.addOneAssumeCapacity().* = .gen(gen.rand),
                .c => cs.addOneAssumeCapacity().* = .gen(gen.rand),
            }
        }
        return .{.{ .a = as.items, .b = bs.items, .c = cs.items }};
    }

    pub fn run(items: S) f32 {
        var ret: f32 = 0.0;
        for (items.a) |*a| {
            a.update();
            ret += a.run();
        }
        for (items.b) |*b| {
            b.update();
            ret += b.run();
        }
        for (items.c) |*c| {
            c.update();
            ret += c.run();
        }
        return ret;
    }
};

test {
    std.testing.refAllDeclsRecursive(@This());
}
