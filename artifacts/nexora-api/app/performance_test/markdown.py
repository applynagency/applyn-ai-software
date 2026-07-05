from app.schemas.performance_test import PerformanceTestOutput


def output_to_markdown(output: PerformanceTestOutput) -> str:
    lines = ["# Performance Test Plan", ""]

    if output.load_test_plan:
        lines.extend(["## Load Test Plan", ""])
        lines.extend(f"- **{item.name}** ({item.id}): {item.description}" for item in output.load_test_plan)
        lines.append("")

    if output.stress_test_plan:
        lines.extend(["## Stress Test Plan", ""])
        lines.extend(f"- **{item.name}** ({item.id}): {item.description}" for item in output.stress_test_plan)
        lines.append("")

    if output.performance_bottlenecks:
        lines.extend(["## Performance Bottlenecks", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.performance_bottlenecks
        )
        lines.append("")

    if output.scaling_recommendations:
        lines.extend(["## Scaling Recommendations", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.scaling_recommendations
        )
        lines.append("")

    if output.caching_recommendations:
        lines.extend(["## Caching Recommendations", ""])
        lines.extend(
            f"- **{item.name}** ({item.id}): {item.description}"
            for item in output.caching_recommendations
        )
        lines.append("")

    return "\n".join(lines)
