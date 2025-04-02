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

def per_size_line(name: str, source: pl.DataFrame, col: str, agg="mean", extent="stdev", scale=alt.Undefined, y_format=alt.Undefined):
    error_bars = alt.Chart(source).mark_errorband(extent=extent).encode(
        alt.X("size").type("ordinal").title("Size"),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        color="kind",
    )
    line = alt.Chart(source).mark_line().encode(
        alt.X("size").type("ordinal").title("Size"),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        color="kind",
    )
    (line + error_bars).save(fig_dir.joinpath(f"{name}-{col}-line-{extent}.png"), scale_factor=4)

scenarios = df.partition_by("scenario", include_key=False, as_dict=True)

for (s,), data in scenarios.items():
    print(s, data)

    for (col, opts) in [
        ("wall_clock", {"scale": "log"}), 
        ("inst_per_cycle", {}), 
        ("cache_miss_rate", {"y_format": "%"}), 
        ("branch_miss_rate", {"y_format": "%"})
        ]:
        per_size_bar(s, data, col, **opts)
        per_size_bar(s, data, col, **opts, extent="ci")
        per_size_line(s, data, col, **opts)
        per_size_line(s, data, col, **opts, extent="ci")