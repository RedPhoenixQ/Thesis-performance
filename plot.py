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
    [scenario, kind, size] = split
    df = pl.read_csv(data_dir.joinpath( name), skip_rows_after_header=5)
    df = df.with_columns(
        pl.lit(part).alias("part"),
        pl.lit(scenario).alias("scenario"),
        pl.lit(kind).alias("kind"),
        pl.lit(int(size)).alias("size"),
    )
    df = df.with_columns((pl.col("scenario") + "-" + pl.col("kind")).alias("test"))
    frames.append(df)

df: pl.DataFrame = pl.concat(frames)
df = df.with_columns(
    (pl.col("instructions") / pl.col("cpu_cycles"))
        .alias("inst_per_cycle"),
    pl.when(pl.col("cache_references") > 0)
        .then((pl.col("cache_misses") / pl.col("cache_references")))
        .otherwise(0)
        .alias("cache_miss_rate"),
    pl.when(pl.col("branch_instructions") > 0)
        .then((pl.col("branch_misses") / pl.col("branch_instructions")))
        .otherwise(0)
        .alias("branch_miss_rate"),
)

summary = df.group_by("size", "part", "scenario", "kind").agg(
    pl.mean("wall_clock"),
    pl.std("wall_clock").name.suffix("_std"),
    pl.mean("inst_per_cycle"),
    pl.std("inst_per_cycle").name.suffix("_std"),
    pl.mean("cache_miss_rate"),
    pl.std("cache_miss_rate").name.suffix("_std"),
    pl.mean("branch_miss_rate"),
    pl.std("branch_miss_rate").name.suffix("_std"),
).sort("size", "part", "scenario", "kind")

summary.write_csv(fig_dir.joinpath("summary.csv"))

def per_size_bar(name: str, source: pl.DataFrame, col: str, agg="mean", extent="stdev", scale=alt.Undefined, y_format=alt.Undefined):
    error_bars = alt.Chart(source).mark_errorbar(extent=extent, ticks=True).encode(
        alt.X("size").type("ordinal").title("Size"),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        xOffset="kind",
    )
    line = alt.Chart(source).mark_bar().encode(
        alt.X("size").type("ordinal").title("Size"),
        alt.Y(col, 
            aggregate=agg,
            scale=alt.Scale(type=scale), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        xOffset="kind",
        color="kind",
    )
    (line + error_bars).save(fig_dir.joinpath(f"{name}-{col}-bar-{extent}.png"), scale_factor=4)

def per_size_line(name: str, source: pl.DataFrame, col: str, agg="mean", extent="stdev", scale=alt.Undefined, y_format=alt.Undefined, color="kind", save=True, chart_layers=[]):
    error_bars = alt.Chart(source).mark_errorband(extent=extent).encode(
        alt.X("size").type("ordinal").title("Size"),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        color=color,
    )
    line = alt.Chart(source).mark_line().encode(
        alt.X("size").type("ordinal").title("Size"),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale), 
            axis=alt.Axis(format=y_format), 
            title=col.replace("_", " ").capitalize(),
        ),
        color=color,
    )
    chart = alt.layer(*chart_layers, line, error_bars)
    if (save):
        chart.save(fig_dir.joinpath(f"{name}-{col}-line-{extent}.png"), scale_factor=4)
    return chart



cache_l1 = alt.Chart(pl.from_dict({"x": (64 * 1024 ) // 24})).mark_rule(strokeDash=[12, 6], size=2).encode(x=alt.X("x", type="ordinal"))
cache_l2 = alt.Chart(pl.from_dict({"x": (256 * 1024 ) // 24})).mark_rule(strokeDash=[12, 6], size=2).encode(x=alt.X("x", type="ordinal"))
cache_l3 = alt.Chart(pl.from_dict({"x": (9 * 1024 * 1024 ) // 24})).mark_rule(strokeDash=[12, 6], size=2).encode(x=alt.X("x", type="ordinal"))
cache_lines = [
    cache_l1, cache_l1.mark_text(text="L1", y=15, dx=-5, align="right", baseline="bottom"),
    cache_l2, cache_l2.mark_text(text="L2", y=15, dx=-5, align="right", baseline="bottom"),
    cache_l3, cache_l3.mark_text(text="L3", y=15, dx=-5, align="right", baseline="bottom"),
]



control_flow_scenarios = df.filter(part="ControlFlow").partition_by("scenario")

alt.layer(*[
    per_size_line("", data, "wall_clock", scale="log", extent="ci", color="test", save=False) 
    for data in control_flow_scenarios
]).save(fig_dir.joinpath("ControlFlow-wall_clock-ci.png"), scale_factor=4)

alt.layer(*[
    per_size_line("", data, "inst_per_cycle", extent="ci", color="test", save=False) 
    for data in control_flow_scenarios
]).save(fig_dir.joinpath("ControlFlow-inst_per_cycle-ci.png"), scale_factor=4)

alt.layer(*cache_lines, *[
    per_size_line("", data, "cache_miss_rate", extent="ci", color="test", save=False) 
    for data in control_flow_scenarios
]).save(fig_dir.joinpath(f"ControlFlow-cache_miss_rate-ci.png"), scale_factor=4)

alt.layer(*[
    per_size_line("", data, "branch_miss_rate", y_format="%", extent="ci", color="test", save=False) 
    for data in control_flow_scenarios
]).save(fig_dir.joinpath(f"ControlFlow-branch_miss_rate-ci.png"), scale_factor=4)



scenarios = df.partition_by("scenario", "part", include_key=False, as_dict=True)
for (s, part), data in scenarios.items():
    print(s)

    for (col, opts) in [
        ("wall_clock", {"scale": "log"}), 
        ("inst_per_cycle", {}), 
        ("cache_miss_rate", {"y_format": "%", "chart_layers": cache_lines}), 
        ("branch_miss_rate", {"y_format": "%"})
        ]:
        per_size_bar(s, data, col, **opts)
        per_size_bar(s, data, col, **opts, extent="ci")
        per_size_line(s, data, col, **opts)
        per_size_line(s, data, col, **opts, extent="ci")