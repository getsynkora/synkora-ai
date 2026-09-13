"""Render the shipped Plotly partial bundles using a real browser, without network."""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[3]


async def main():
    results = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            for family, charts in {
                "cartesian": [
                    {"type": "heatmap", "z": [[1, 2], [3, 4]]},
                    {"type": "box", "y": [1, 2, 3, 4]},
                    {"type": "violin", "y": [1, 2, 3, 4]},
                ],
                "finance": [
                    {"type": "candlestick", "x": [1, 2], "open": [1, 2], "high": [3, 4], "low": [0, 1], "close": [2, 3]},
                    {"type": "waterfall", "x": ["a", "b"], "y": [1, 2]},
                ],
            }.items():
                page = await browser.new_page()
                await page.route("**/*", lambda route: route.abort())
                await page.set_content('<div id="chart" style="width:600px;height:400px"></div>')
                package = ROOT / "web/node_modules" / f"plotly.js-{family}-dist-min"
                await page.add_script_tag(path=str(package / f"plotly-{family}.min.js"))
                for data in charts:
                    result = await page.evaluate('''async data => {
                        const node = document.getElementById('chart');
                        await Plotly.react(node, [data], {}, {displayModeBar:false});
                        const types = Object.keys(Plotly.PlotSchema.get().traces);
                        return {type:node._fullData[0].type,svg:!!node.querySelector('svg'),hasMaps:types.some(type => /^(scatter|choropleth|density)map/.test(type))};
                    }''', data)
                    assert result == {"type": data["type"], "svg": True, "hasMaps": False}, result
                    results.append(result)
                await page.close()
        finally:
            await browser.close()
    print(json.dumps(results))


asyncio.run(main())
