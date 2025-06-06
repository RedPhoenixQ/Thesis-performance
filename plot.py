import argparse
import itertools
from pathlib import Path
import altair as alt
import polars as pl
import scipy.stats as stats 
import glob

def per_size_bar(name: str, source: pl.DataFrame, col: str, agg="mean", extent="stdev", scale=alt.Undefined, y_format=alt.Undefined, chart_layers=None):
    error_bars = alt.Chart(source).mark_errorbar(extent=extent, ticks=True).encode(
        alt.X("number_of_items", type="ordinal", title="Number of Item"),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale, base=2), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        xOffset="Kind",
    )
    line = alt.Chart(source).mark_bar().encode(
        alt.X("number_of_items", type="ordinal", title="Number of Item"),
        alt.Y(col, 
            aggregate=agg,
            scale=alt.Scale(type=scale, base=2), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize(),
        ),
        xOffset="Kind",
        color="Kind",
    )
    (line + error_bars).save(fig_dir.joinpath(f"{name}-{col}-bar-{extent}.png"), scale_factor=4)

def per_size_line(name: str, source: pl.DataFrame, col: str, agg="mean", extent="stdev", scale=alt.Undefined, y_format=alt.Undefined, y_title=None, color="Kind", dash=alt.Undefined, save=True, chart_layers=[]):
    error_bars = alt.Chart(source).mark_errorband(extent=extent).encode(
        alt.X("number_of_items", type="quantitative", title="Number of Items", scale=alt.Scale(type="log", base=2, paddingOuter=0)),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale, base=2), 
            axis=alt.Axis(format=y_format),
            title=col.replace("_", " ").capitalize() if y_title is None else y_title,
        ),
        color=color,
    )
    line = alt.Chart(source).mark_line().encode(
        alt.X("number_of_items", type="quantitative", title="Number of Items", scale=alt.Scale(type="log", base=2)),
        alt.Y(col,
            aggregate=agg,
            scale=alt.Scale(type=scale, base=2), 
            axis=alt.Axis(format=y_format), 
            title=col.replace("_", " ").capitalize() if y_title is None else y_title,
        ),
        alt.StrokeDash(field=dash),
        color=color,
    )
    chart = alt.layer(*chart_layers, line, error_bars)
    if (save):
        chart.save(fig_dir.joinpath(f"{name}-{col}-line-{extent}.png"), scale_factor=4)
    return chart

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
    [test, kind, num_items] = split
    df = pl.read_csv(data_dir.joinpath( name), skip_rows_after_header=5)
    match test:
        case "DynamicDispatch":
            test = "DD"
        case "EnumTaggedDispatch":
            test = "ETD"
        case "ExistentialProcessing":
            test = "EP"
    df = df.with_columns(
        pl.lit(part).alias("Part"),
        pl.lit(test).alias("Test"),
        pl.lit(kind).alias("Kind"),
        pl.lit(int(num_items)).alias("number_of_items"),
    )
    df = df.with_columns((pl.col("Test") + "-" + pl.col("Kind")).alias("Scenario"))
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
).sort("number_of_items", "Part", "Test", "Kind")

# Summary stats
df.group_by("number_of_items", "Part", "Test", "Kind", maintain_order=True).agg(
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
).write_csv(fig_dir.joinpath("summary.csv"))

# Instructions per item stats
(df.with_columns(instructions_per_item=pl.col("instructions") / pl.col("number_of_items"))
    .group_by("Part", "Scenario", maintain_order=True)
    .agg(pl.mean("instructions_per_item"), pl.std("instructions_per_item").name.suffix("_std"))
).write_csv(fig_dir.joinpath("instructions.csv"))

layout_tests = df.filter(Part="Layout")
control_flow_tests = df.filter(Part="ControlFlow")

correlation = []
for (Scenario,), data in df.partition_by("Scenario", as_dict=True, maintain_order=True).items():
    pearson = stats.pearsonr(data.get_column("execution_time"), data.get_column("cache_miss_rate"))
    spearman = stats.spearmanr(data.get_column("execution_time"), data.get_column("cache_miss_rate"))
    kendall = stats.kendalltau(data.get_column("execution_time"), data.get_column("cache_miss_rate"))
    correlation.append({
        "Scenario": Scenario,
        "pearson_p": pearson.pvalue,
        "pearson_stat": pearson.statistic,
        "spearman_p": spearman.pvalue,
        "spearman_stat": spearman.statistic,
        "kendall_p": kendall.pvalue,
        "kendall_stat": kendall.statistic,
    })
pl.from_dicts(correlation).write_csv(fig_dir.joinpath("Correlation-cache_miss_rate-execution_time.csv"))

correlation = []
for (Scenario,), data in df.partition_by("Scenario", as_dict=True, maintain_order=True).items():
    pearson = stats.pearsonr(data.get_column("execution_time"), data.get_column("branch_miss_rate"))
    spearman = stats.spearmanr(data.get_column("execution_time"), data.get_column("branch_miss_rate"))
    kendall = stats.kendalltau(data.get_column("execution_time"), data.get_column("branch_miss_rate"))
    correlation.append({
        "Scenario": Scenario,
        "pearson_p": pearson.pvalue,    
        "pearson_stat": pearson.statistic,
        "spearman_p": spearman.pvalue,
        "spearman_stat": spearman.statistic,
        "kendall_p": kendall.pvalue,
        "kendall_stat": kendall.statistic,
    })
pl.from_dicts(correlation).write_csv(fig_dir.joinpath("Correlation-branch_miss_rate-execution_time.csv"))

correlation = []
for (Scenario,), data in df.partition_by("Scenario", as_dict=True, maintain_order=True).items():
    pearson = stats.pearsonr(data.get_column("instructions_per_cycle"), data.get_column("cache_miss_rate"))
    spearman = stats.spearmanr(data.get_column("instructions_per_cycle"), data.get_column("cache_miss_rate"))
    kendall = stats.kendalltau(data.get_column("instructions_per_cycle"), data.get_column("cache_miss_rate"))
    correlation.append({
        "Scenario": Scenario,
        "pearson_p": pearson.pvalue,
        "pearson_stat": pearson.statistic,
        "spearman_p": spearman.pvalue,
        "spearman_stat": spearman.statistic,
        "kendall_p": kendall.pvalue,
        "kendall_stat": kendall.statistic,
    })
pl.from_dicts(correlation).write_csv(fig_dir.joinpath("Correlation-cache_miss_rate-IPC.csv"))

correlation = []
for (Scenario,), data in df.partition_by("Scenario", as_dict=True, maintain_order=True).items():
    pearson = stats.pearsonr(data.get_column("instructions_per_cycle"), data.get_column("branch_miss_rate"))
    spearman = stats.spearmanr(data.get_column("instructions_per_cycle"), data.get_column("branch_miss_rate"))
    kendall = stats.kendalltau(data.get_column("instructions_per_cycle"), data.get_column("branch_miss_rate"))
    correlation.append({
        "Scenario": Scenario,
        "pearson_p": pearson.pvalue,
        "pearson_stat": pearson.statistic,
        "spearman_p": spearman.pvalue,
        "spearman_stat": spearman.statistic,
        "kendall_p": kendall.pvalue,
        "kendall_stat": kendall.statistic,
    })
pl.from_dicts(correlation).write_csv(fig_dir.joinpath("Correlation-branch_miss_rate-IPC.csv"))

times = control_flow_tests.select("Scenario", "number_of_items", "execution_time").partition_by("number_of_items", as_dict=True, include_key=False, maintain_order=True)
anova = {}
for (num_items, ), parts in times.items():
    res = stats.f_oneway(*(data.get_column("execution_time") for data in parts.partition_by("Scenario")))
    anova[str(num_items)] = res.pvalue
pl.from_dict(anova).write_csv(fig_dir.joinpath("ControlFlow-execution_time-anova.csv"))

tukey = []
for (num_items, ), parts in times.items():
    scenarios = parts.partition_by("Scenario", as_dict=True, maintain_order=True)
    keys = [key for (key,) in scenarios.keys()]
    res = stats.tukey_hsd(*(data.get_column("execution_time") for data in scenarios.values()))
    tukey.append({ "number_of_items": str(num_items), } | {
        f"{keys[i]} - {keys[j]}": res.pvalue[i, j]
        for (i,j) in itertools.combinations(range(len(keys)), 2)
    })
pl.from_dicts(tukey).transpose(include_header=True, header_name="Combinations", column_names="number_of_items").write_csv(fig_dir.joinpath("ControlFlow-execution_time-tukey.csv"))

# Indicator line for cache sizes
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

layout_kinds = layout_tests.select("Test", "Kind", "execution_time", "number_of_items").partition_by("Kind", as_dict=True, maintain_order=True)
layout_diff = layout_kinds.get(("AoS",)).rename({"execution_time": "AoS"}).hstack([layout_kinds.get(("SoA",)).get_column("execution_time").alias("SoA")])
diff = (layout_diff.group_by("Test", "number_of_items").agg(diff=pl.lit(1) - pl.mean("SoA") / pl.mean("AoS")))
per_size_line("Layout-execution_time", diff, "diff", color="Test", y_format="%", y_title="SoA execution time compared to AoS", chart_layers=cache_lines)

diff.select("Test", "number_of_items", "diff").write_csv(fig_dir.joinpath("Layout-execution_time-diff.csv"))

# T-test AoS vs SoA
layout_diff.sort("Test", "number_of_items").group_by("Test", "number_of_items", maintain_order=True).map_groups(
    lambda group: pl.from_dict({
        "Test": group.get_column("Test").first(),
        "number_of_items": group.get_column("number_of_items").first(),
        "pvalue": stats.ttest_ind(group.get_column("SoA"), group.get_column("AoS"), equal_var=False).pvalue
    })
).pivot("number_of_items", index="Test", values="pvalue").write_csv(fig_dir.joinpath("Layout-execution_time-ttest-pvalue.csv"))

diff = control_flow_tests.join(
    control_flow_tests.filter(Scenario="DD-unsorted").group_by("number_of_items").agg(DD_mean=pl.mean("execution_time")), 
    on="number_of_items"
).group_by("Scenario", "Kind", "number_of_items").agg(diff=pl.lit(1) - pl.mean("execution_time") / pl.first("DD_mean"))
per_size_line("ControlFlow-execution_time", diff, "diff", color="Scenario", dash="Kind", y_format="%", chart_layers=cache_lines)

for extent in ["ci", "stdev"]:
    # Layout
    per_size_line("Layout", layout_tests, "execution_time", scale="log", extent=extent, color="Scenario", dash="Kind", chart_layers=cache_lines) 
    per_size_line("Layout", layout_tests, "instructions_per_cycle", extent=extent, color="Scenario", dash="Kind", chart_layers=cache_lines) 
    per_size_line("Layout", layout_tests, "cache_miss_rate", y_format="%", extent=extent, color="Scenario", dash="Kind", chart_layers=cache_lines) 

    # Control flow
    per_size_line("ControlFlow", control_flow_tests, "execution_time", scale="log", extent=extent, color="Scenario", dash="Kind", chart_layers=cache_lines)
    per_size_line("ControlFlow", control_flow_tests, "instructions_per_cycle", extent=extent, color="Scenario", dash="Kind", chart_layers=cache_lines) 
    per_size_line("ControlFlow", control_flow_tests, "cache_miss_rate", y_format="%", extent=extent, color="Scenario", dash="Kind", chart_layers=cache_lines) 
    per_size_line("ControlFlow", control_flow_tests, "branch_miss_rate", y_format="%", extent=extent, color="Scenario", dash="Kind", chart_layers=cache_lines) 
