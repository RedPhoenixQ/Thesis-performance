import argparse
from pathlib import Path
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
    (pl.when(pl.col("cache_references") > 0)
        .then(1 - (pl.col("cache_misses") / pl.col("cache_references")))
        .otherwise(1)
        .alias("cache_hit_rate"),
    )
)

sizes = df.get_column("size").unique()
columns = list(filter(lambda c: c not in ["part", "scenario", "test", "kind", "size"], df.columns))

layout = df.filter(part="Layout")
controlflow = df.filter(part="ControlFlow")

lscenarios = layout.get_column("scenario").unique()
lkind = layout.get_column("kind").unique()

for s in lscenarios:
    source = layout.filter(pl.col("scenario") == s)

    print(source)

    error_bars = alt.Chart(source).mark_errorband(extent="ci").encode(
        alt.X("size").type("ordinal"),
        alt.Y("cache_hit_rate").aggregate("mean"),
        color="kind",
    )
    line = alt.Chart(source).mark_line().encode(
        alt.X("size").type("ordinal"),
        alt.Y("cache_hit_rate").aggregate("mean"),
        color="kind",
    )
    (error_bars + line).save(fig_dir.joinpath(s + "-cache_hit_rate.png"), scale_factor=4)
    
    
    error_bars = alt.Chart(source).mark_errorbar(extent="stdev", ticks=True).encode(
        alt.X("size").type("ordinal"),
        alt.Y("cache_hit_rate").aggregate("average"),
        xOffset="kind",
    )
    line = alt.Chart(source).mark_bar().encode(
        alt.X("size").type("ordinal"),
        alt.Y("cache_hit_rate").aggregate("average"),
        xOffset="kind",
        color="kind",
    )
    (line + error_bars).save(fig_dir.joinpath(s + "-cache_hit_rate-bar-stdev.png"), scale_factor=4)
    
    error_bars = alt.Chart(source).mark_errorbar(extent="ci", ticks=True).encode(
        alt.X("size").type("ordinal"),
        alt.Y("cache_hit_rate").aggregate("mean"),
        xOffset="kind",
    )
    line = alt.Chart(source).mark_bar().encode(
        alt.X("size").type("ordinal"),
        alt.Y("cache_hit_rate").aggregate("mean"),
        xOffset="kind",
        color="kind",
    )
    (line + error_bars).save(fig_dir.joinpath(s + "-cache_hit_rate-bar-ci.png"), scale_factor=4)


    error_bars = alt.Chart(source).mark_errorband(extent="stdev").encode(
        alt.X("size").type("ordinal"),
        alt.Y("cpu_cycles").aggregate("mean").scale(type="log"),
        color="kind",
    )
    line = alt.Chart(source).mark_line().encode(
        alt.X("size").type("ordinal"),
        alt.Y("cpu_cycles").aggregate("mean").scale(type="log"),
        color="kind",
    )
    (line + error_bars).save(fig_dir.joinpath(s + "-cpu_cycles-line-stdev.png"), scale_factor=4)
    
    error_bars = alt.Chart(source).mark_errorbar(extent="stdev", ticks=True).encode(
        alt.X("size").type("ordinal"),
        alt.Y("cpu_cycles").aggregate("average").scale(type="log"),
        xOffset="kind",
    )
    line = alt.Chart(source).mark_bar().encode(
        alt.X("size").type("ordinal"),
        alt.Y("cpu_cycles").aggregate("average").scale(type="log"),
        xOffset="kind",
        color="kind",
    )
    (line + error_bars).save(fig_dir.joinpath(s + "-cpu_cycles-bar-stdev.png"), scale_factor=4)

    error_bars = alt.Chart(source).mark_errorbar(extent="ci", ticks=True).encode(
        alt.X("size").type("ordinal"),
        alt.Y("cpu_cycles").aggregate("mean").scale(type="log"),
        xOffset="kind",
    )
    line = alt.Chart(source).mark_bar().encode(
        alt.X("size").type("ordinal"),
        alt.Y("cpu_cycles").aggregate("mean").scale(type="log"),
        xOffset="kind",
        color="kind",
    )
    (line + error_bars).save(fig_dir.joinpath(s + "-cpu_cycles-bar-ci.png"), scale_factor=4)