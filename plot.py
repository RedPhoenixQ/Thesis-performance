import argparse
from pathlib import Path
from typing import Optional
import altair as alt
import polars as pl
import glob

ap = argparse.ArgumentParser()
ap.add_argument("directory", type=Path)
args = ap.parse_args()

data_dir: Path = args.directory.joinpath("data")
fig_dir: Path = args.directory.joinpath("figures")

fig_dir.mkdir(exist_ok=True)

filenames = glob.glob("*.csv", root_dir=data_dir)

assert len(filenames) > 0

frames = []

for name in filenames:
    print(name)
    [part, rest, _] = name.split(".")
    split = rest.split("-")
    if len(split) == 4:
        split.pop()
    [test, kind, size] = split
    df = pl.read_csv(data_dir.joinpath( name), skip_rows_after_header=5)
    df = df.with_columns(
        pl.lit(part).alias("part"),
        pl.lit(test).alias("test"),
        pl.lit(kind).alias("kind"),
        pl.lit(int(size)).alias("size"),
    )
    df = df.with_columns((pl.col("test") + "-" + pl.col("kind")).alias("Scenario"))
    frames.append(df)

df: pl.DataFrame = pl.concat(frames)
df = df.with_columns(
    (pl.col("instructions") / pl.col("cpu_cycles"))
        .alias("instructions_per_cycle"),
    pl.when(pl.col("cache_references") > 0)
        .then((pl.col("cache_misses") / pl.col("cache_references")))
        .otherwise(0)
        .alias("cache_miss_rate"),
    pl.when(pl.col("branch_instructions") > 0)
        .then((pl.col("branch_misses") / pl.col("branch_instructions")))
        .otherwise(0)
        .alias("branch_miss_rate"),
)

# points = alt.Chart(df.filter(part="ControlFlow")).mark_point().encode(
#     alt.X("wall_clock", scale=alt.Scale(type="log")),
#     alt.Y("branch_miss_rate"),
#     color="Scenario",
# )
# regressions = [points.transform_regression("instructions_per_cycle", "branch_miss_rate", groupby=["Scenario"], method="poly", order=4)
#     .mark_line()
#     .encode(color="Scenario")
# ]
# alt.layer(points,).save(fig_dir.joinpath("branch_miss_rate-scatter.png"), scale_factor=4)

# points = alt.Chart(df.filter(part="ControlFlow")).mark_point().encode(
#     alt.X("wall_clock", scale=alt.Scale(type="log")),
#     alt.Y("cache_miss_rate"),
#     color="Scenario",
# )
# regressions = [points.transform_regression("instructions_per_cycle", "cache_miss_rate", groupby=["Scenario"], method="linear")
#     .mark_line()
#     .encode(color="Scenario")
# ]
# alt.layer(points, ).save(fig_dir.joinpath("cache_miss_rate-scatter.png"), scale_factor=4)

summary = df.group_by("size", "part", "test", "kind").agg(
    pl.mean("wall_clock"),
    pl.std("wall_clock").name.suffix("_std"),
    pl.mean("instructions_per_cycle"),
    pl.std("instructions_per_cycle").name.suffix("_std"),
    pl.mean("cache_miss_rate"),
    pl.std("cache_miss_rate").name.suffix("_std"),
    pl.mean("branch_miss_rate"),
    pl.std("branch_miss_rate").name.suffix("_std"),
).sort("size", "part", "test", "kind")

summary.write_csv(fig_dir.joinpath("summary.csv"))

def per_size_bar(name: str, source: pl.DataFrame, col: str, agg="mean", extent="stdev", scale=alt.Undefined, y_format=alt.Undefined, chart_layers=None):
    error_bars = alt.Chart(source).mark_errorbar(extent=extent, ticks=True).encode(
        alt.X("size", type="ordinal", title="Size"),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale, base=2), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        xOffset="kind",
    )
    line = alt.Chart(source).mark_bar().encode(
        alt.X("size", type="ordinal", title="Size"),
        alt.Y(col, 
            aggregate=agg,
            scale=alt.Scale(type=scale, base=2), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        xOffset="kind",
        color="kind",
    )
    (line + error_bars).save(fig_dir.joinpath(f"{name}-{col}-bar-{extent}.png"), scale_factor=4)

def per_size_line(name: str, source: pl.DataFrame, col: str, agg="mean", extent="stdev", scale=alt.Undefined, y_format=alt.Undefined, color="kind", save=True, chart_layers=[]):
    error_bars = alt.Chart(source).mark_errorband(extent=extent).encode(
        alt.X("size", type="quantitative", title="Size", scale=alt.Scale(type="log", base=2, paddingOuter=0)),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale, base=2), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        color=color,
    )
    line = alt.Chart(source).mark_line().encode(
        alt.X("size", type="quantitative", title="Size", scale=alt.Scale(type="log", base=2)),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale, base=2), 
            axis=alt.Axis(format=y_format), 
            title=col.replace("_", " ").capitalize(),
        ),
        color=color,
    )
    chart = alt.layer(*chart_layers, line, error_bars)
    if (save):
        chart.save(fig_dir.joinpath(f"{name}-{col}-line-{extent}.png"), scale_factor=4)
    return chart



cache_lines = [
    alt.Chart(pl.from_dict({"x": cache_size // 24}))
        .mark_rule(strokeDash=[12, 6], size=2)
        .encode(alt.X("x", type="quantitative", scale=alt.Scale(type="log", base=2)))
    for cache_size in [(64 * 1024), (256 * 1024), (9 * 1024 * 1024)]
]
cache_lines.extend([
    line.mark_text(text="L" + str(i), y=15, dx=-5, align="right", baseline="bottom")
    for i, line in enumerate(cache_lines)
])



control_flow_tests = df.filter(part="ControlFlow").partition_by("test")

alt.layer(*cache_lines, *[
    per_size_line("", data, "wall_clock", scale="log", extent="ci", color="Scenario", save=False) 
    for data in control_flow_tests
]).save(fig_dir.joinpath("ControlFlow-wall_clock-ci.png"), scale_factor=4)

alt.layer(*cache_lines, *[
    per_size_line("", data, "instructions_per_cycle", extent="ci", color="Scenario", save=False) 
    for data in control_flow_tests
]).save(fig_dir.joinpath("ControlFlow-instructions_per_cycle-ci.png"), scale_factor=4)

alt.layer(*cache_lines, *[
    per_size_line("", data, "cache_miss_rate", y_format="%", extent="ci", color="Scenario", save=False) 
    for data in control_flow_tests
]).save(fig_dir.joinpath(f"ControlFlow-cache_miss_rate-ci.png"), scale_factor=4)

alt.layer(*cache_lines, *[
    per_size_line("", data, "branch_miss_rate", y_format="%", extent="ci", color="Scenario", save=False) 
    for data in control_flow_tests
]).save(fig_dir.joinpath(f"ControlFlow-branch_miss_rate-ci.png"), scale_factor=4)

alt.layer(*cache_lines, *[
    per_size_line("", data, "instructions", scale="log", extent="stdev", color="Scenario", save=False) 
    for data in control_flow_tests
]).save(fig_dir.joinpath(f"ControlFlow-instructions-stdev.png"), scale_factor=4)


# layout_tests = df.filter(part="Layout").partition_by("test")

# alt.layer(*cache_lines, *[
#     per_size_line("", data, "wall_clock", scale="log", extent="ci", color="Scenario", save=False) 
#     for data in layout_tests
# ]).save(fig_dir.joinpath("Layout-wall_clock-ci.png"), scale_factor=4)

# alt.layer(*cache_lines, *[
#     per_size_line("", data, "instructions_per_cycle", extent="ci", color="Scenario", save=False) 
#     for data in layout_tests
# ]).save(fig_dir.joinpath("Layout-instructions_per_cycle-ci.png"), scale_factor=4)

# alt.layer(*cache_lines, *cache_lines, *[
#     per_size_line("", data, "cache_miss_rate", y_format="%", extent="ci", color="Scenario", save=False) 
#     for data in layout_tests
# ]).save(fig_dir.joinpath(f"Layout-cache_miss_rate-ci.png"), scale_factor=4)

# alt.layer(*cache_lines, *[
#     per_size_line("", data, "branch_miss_rate", y_format="%", extent="ci", color="Scenario", save=False) 
#     for data in layout_tests
# ]).save(fig_dir.joinpath(f"Layout-branch_miss_rate-ci.png"), scale_factor=4)



scenarios = df.partition_by("test", include_key=False, as_dict=True)
for (s,), data in scenarios.items():
    print(s)

    for (col, opts) in [
        ("wall_clock", {"scale": "log", "chart_layers": cache_lines}), 
        ("instructions_per_cycle", {"chart_layers": cache_lines}), 
        ("cache_miss_rate", {"y_format": "%", "chart_layers": cache_lines}), 
        ("branch_miss_rate", {"y_format": "%", "chart_layers": cache_lines})
        ]:
        per_size_bar(s, data, col, **opts)
        per_size_bar(s, data, col, **opts, extent="ci")
        per_size_line(s, data, col, **opts)
        per_size_line(s, data, col, **opts, extent="ci")