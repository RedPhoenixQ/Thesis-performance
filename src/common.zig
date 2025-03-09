const std = @import("std");

pub fn ArgTypes(comptime T: anytype) type {
    switch (@typeInfo(@TypeOf(T))) {
        .@"fn" => |f| {
            var args: [f.params.len]type = undefined;
            for (f.params, &args) |param, *arg| {
                arg.* = param.type orelse void;
            }
            return std.meta.Tuple(&args);
        },
        else => @compileError("T must be a function"),
    }
}

pub fn ReturnType(comptime T: anytype) type {
    switch (@typeInfo(@TypeOf(T))) {
        .@"fn" => |f| return f.return_type orelse void,
        else => @compileError("T must be a function"),
    }
}
