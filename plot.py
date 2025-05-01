import argparse
import itertools
from pathlib import Path
import altair as alt
import polars as pl
import scipy.stats as stats 
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
    match test:
        case "DynamicDispatch":
            test = "DD"
        case "EnumTaggedDispatch":
            test = "ETD"
        case "ExistentialProcessing":
            test = "EP"
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
#     alt.X("execution_time", scale=alt.Scale(type="log")),
#     alt.Y("branch_miss_rate"),
#     color="Scenario",
# )
# regressions = [points.transform_regression("instructions_per_cycle", "branch_miss_rate", groupby=["Scenario"], method="poly", order=4)
#     .mark_line()
#     .encode(color="Scenario")
# ]
# alt.layer(points,).save(fig_dir.joinpath("branch_miss_rate-scatter.png"), scale_factor=4)

# points = alt.Chart(df.filter(part="ControlFlow")).mark_point().encode(
#     alt.X("execution_time", scale=alt.Scale(type="log")),
#     alt.Y("cache_miss_rate"),
#     color="Scenario",
# )
# regressions = [points.transform_regression("instructions_per_cycle", "cache_miss_rate", groupby=["Scenario"], method="linear")
#     .mark_line()
#     .encode(color="Scenario")
# ]
# alt.layer(points, ).save(fig_dir.joinpath("cache_miss_rate-scatter.png"), scale_factor=4)

summary = df.group_by("size", "part", "test", "kind").agg(
    pl.mean("cpu_cycles"),
    pl.std("cpu_cycles").name.suffix("_std"),
    pl.mean("execution_time"),
    pl.std("execution_time").name.suffix("_std"),
    pl.mean("instructions_per_cycle"),
    pl.std("instructions_per_cycle").name.suffix("_std"),
    pl.mean("cache_miss_rate"),
    pl.std("cache_miss_rate").name.suffix("_std"),
    pl.mean("branch_miss_rate"),
    pl.std("branch_miss_rate").name.suffix("_std"),
).sort("size", "part", "test", "kind")

summary.write_csv(fig_dir.joinpath("summary.csv"))

times = df.filter(part="Layout").select("test", "kind", "size", "execution_time").partition_by("test", as_dict=True, include_key=False)

ttest = {
    "size": summary.get_column("size").unique(maintain_order=True).cast(pl.String)
}
for (name, ), data in times.items():
    data_parts = data.partition_by("kind", as_dict=True, include_key=False)
    one = data_parts.get(("SoA",)).select("size", time_SoA="execution_time")
    two = data_parts.get(("AoS",)).select(time_AoS="execution_time")
    cmp = one.hstack(two)

    sizes = cmp.sort("size").partition_by("size", maintain_order=True)
    tests = [
        stats.ttest_ind(size.get_column("time_SoA"), size.get_column("time_AoS"), equal_var=False)
        for size in sizes
    ]
    # ttest[f"{name}-stats"] = [test.statistic for test in tests]
    ttest[name] = [test.pvalue for test in tests]

ttest = pl.from_dict(ttest).transpose(include_header=True, header_name="Combinations", column_names="size")
ttest.write_csv(fig_dir.joinpath("Layout-execution_time-ttest-pvalue.csv"))

times = (df.filter(part="ControlFlow")
    .select("Scenario", "size", "execution_time")
    .sort("size", "Scenario")
    .partition_by("size", as_dict=True, include_key=False, maintain_order=True)
)
anova = {}
for (size, ), parts in times.items():
    res = stats.f_oneway(*(data.get_column("execution_time") for data in parts.partition_by("Scenario")))
    anova[str(size)] = res.pvalue
pl.from_dict(anova).write_csv(fig_dir.joinpath("ControlFlow-execution_time-anova.csv"))


tukey = []
for (size, ), parts in times.items():
    scenarios = parts.partition_by("Scenario", as_dict=True, maintain_order=True)
    keys = [key for (key,) in scenarios.keys()]
    res = stats.tukey_hsd(*(data.get_column("execution_time") for data in scenarios.values()))
    tukey.append({ "size": str(size), } | {
        f"{keys[i]} - {keys[j]}": res.pvalue[i, j]
        for (i,j) in itertools.combinations(range(len(keys)), 2)
    })
pl.from_dicts(tukey).transpose(include_header=True, header_name="Combinations", column_names="size").write_csv(fig_dir.joinpath("ControlFlow-execution_time-tukey.csv"))

(df.with_columns(instructions_per_item=pl.col("instructions") / pl.col("size"))
    .group_by("part", "Scenario")
    .agg(pl.mean("instructions_per_item"), pl.std("instructions_per_item").name.suffix("_std"))
    .sort("part", "Scenario")
).write_csv(fig_dir.joinpath("instructions.csv"))

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
    alt.Chart(pl.from_dict({"x": cache_size // 16}))
        .mark_rule(strokeDash=[12, 6], size=2)
        .encode(alt.X("x", type="quantitative", scale=alt.Scale(type="log", base=2)))
    for cache_size in [(64 * 1024), (256 * 1024), (9 * 1024 * 1024)]
]
cache_lines.extend([
    line.mark_text(text="L" + str(i), y=15, dx=-5, align="right", baseline="bottom")
    for i, line in enumerate(cache_lines, 1)
])



control_flow_tests = df.filter(part="ControlFlow").partition_by("test")

alt.layer(*cache_lines, *[
    per_size_line("", data, "execution_time", scale="log", extent="ci", color="Scenario", save=False) 
    for data in control_flow_tests
]).save(fig_dir.joinpath("ControlFlow-execution_time-ci.png"), scale_factor=4)

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


# layout_tests = df.filter(part="Layout").partition_by("test")

# alt.layer(*cache_lines, *[
#     per_size_line("", data, "execution_time", scale="log", extent="ci", color="Scenario", save=False) 
#     for data in layout_tests
# ]).save(fig_dir.joinpath("Layout-execution_time-ci.png"), scale_factor=4)

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
        ("execution_time", {"scale": "log", "chart_layers": cache_lines}), 
        ("instructions_per_cycle", {"chart_layers": cache_lines}), 
        ("cache_miss_rate", {"y_format": "%", "chart_layers": cache_lines}), 
        ("branch_miss_rate", {"y_format": "%", "chart_layers": cache_lines})
        ]:
        per_size_bar(s, data, col, **opts)
        per_size_bar(s, data, col, **opts, extent="ci")
        per_size_line(s, data, col, **opts)
        per_size_line(s, data, col, **opts, extent="ci")