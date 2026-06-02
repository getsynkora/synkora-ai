"""Register infographic generation tools."""

from __future__ import annotations


def register_infographic_tools(registry) -> None:
    """Register infographic generation tools with the ADK tool registry."""
    from src.services.agents.internal_tools.infographic_tools import (
        internal_generate_infographic,
        internal_generate_slack_infographic,
    )

    registry.register_tool(
        name="internal_generate_infographic",
        description=(
            "Generate a data-driven infographic from a structured JSON spec and upload it to S3.\n\n"
            "IMPORTANT: After calling this tool the infographic image is automatically rendered in the chat UI — "
            "do NOT describe it as a table or embed any image URL in your response. Simply say the infographic has been generated.\n\n"
            "Use this after querying the knowledge base or Slack to produce a visual report "
            "(CEO briefing, weekly digest, channel activity summary, etc.).\n\n"
            "━━ THEMES ━━\n"
            "Named presets (pass as string): aurora | midnight | carbon | sunset | emerald | daylight\n"
            "Legacy aliases also work: dark → midnight, light → daylight, glass → aurora.\n"
            "daylight — clean light background, editorial typography, pastel palette. Use for lifestyle, health, habits, and editorial infographics.\n"
            'Custom dict: {"bg":"#0B0B0D","palette":["#F97316","#3B82F6"],"card_bg":"#131316",...}\n'
            'Partial override: {"preset":"midnight","palette":["#custom1","#custom2"]}\n\n'
            "━━ SECTION TYPES ━━\n\n"
            "kpi_row — Row of stat cards (numbers + labels + optional trend badge)\n"
            '  {"type":"kpi_row","items":[{"label":"Messages","value":342,"change":"+12%","trend":"up"}]}\n'
            "  trend: 'up' (green arrow) | 'down' (red arrow) | omit\n\n"
            "bar_chart — Horizontal bar chart comparing values across categories\n"
            '  {"type":"bar_chart","title":"Channel Activity","data":[\n'
            '    {"label":"#engineering","value":120},\n'
            '    {"label":"#sales","value":80,"color":"#10B981"}\n'
            "  ]}\n\n"
            "donut — Donut chart for proportional data with legend\n"
            '  {"type":"donut","title":"Message Distribution","data":[\n'
            '    {"label":"Engineering","value":120},\n'
            '    {"label":"Sales","value":80}\n'
            "  ]}\n\n"
            "stories — Numbered story cards (headline + body + channel/author)\n"
            '  {"type":"stories","title":"Top Stories","items":[\n'
            '    {"headline":"PR #412 merged","body":"Auth overhaul done. Latency -40%.","channel":"#eng","author":"Alice"}\n'
            "  ]}\n\n"
            "heatmap — 7-day x 24-hour activity grid\n"
            '  {"type":"heatmap","title":"Hourly Activity","data":[[0,0,0,1,2,0,...], ...]}\n'
            "  data must be a list of 7 lists, each with exactly 24 integer values.\n"
            "  row_labels: optional list of 7 day names (default Mon–Sun)\n\n"
            "divider — Horizontal rule with optional label\n"
            '  {"type":"divider"} or {"type":"divider","label":"This Week"}\n\n'
            "text — Plain paragraph\n"
            '  {"type":"text","content":"Free-form text shown as a paragraph."}\n\n'
            "sustainability_dashboard — Full clean editorial ESG dashboard matching the sustainability-report reference style.\n"
            '  {"type":"sustainability_dashboard","brand":"EcoFuture","report_label":"Sustainability Report 2024",'
            '   "title":"Building a Sustainable Tomorrow","subtitle":"Our 2024 highlights...",'
            '   "stats":[{"label":"Trees Planted","value":"1.2M","icon_name":"leaf"}],'
            '   "impacts":[{"title":"Environmental Stewardship","value":92,"icon_name":"leaf"}],'
            '   "emissions":{"value":"18,754","series":[5000,10800,13200,16700,20700],"x_labels":["2020","2021","2022","2023","2024"]}}\n\n'
            "assessment_scorecard — Compact flat assessment certificate by default; use layout:'classic' for the older card-heavy scorecard.\n"
            '  {"type":"assessment_scorecard","badge":"AI Threat Certificate","title":"AI Threat Assessment",'
            '   "score":84,"max_score":100,"status":"Critical","risk_label":"High Risk",'
            '   "risk_items":[{"title":"Test case execution","value":95,"status":"Critical"}],'
            '   "risk_drivers":[{"label":"Test execution","value":95}],"tools":["Testim","Mabl","Applitools"],'
            '   "summary_cards":[{"value":"84","label":"Replacement Score"}],'
            '   "recommendation":{"title":"Shift into higher judgment work","icon_name":"target"}}\n'
            '  Legacy layout: {"type":"assessment_scorecard","layout":"classic","title":"AI Readiness Assessment",'
            '   "score":87,"status":"Excellent","categories":[{"title":"Infrastructure","value":92,"status":"Excellent"}]}\n\n'
            "showcase_dashboard — Colorful multi-card executive dashboard matching the vivid six-panel reference style.\n"
            '  {"type":"showcase_dashboard","cards":[\n'
            '    {"variant":"business_performance","title":"Q2 Business Performance","overall":{"value":"87%","status":"Excellent"}},\n'
            '    {"variant":"sustainability_impact","title":"Sustainability Impact Report 2024"},\n'
            '    {"variant":"customer_satisfaction","title":"Customer Satisfaction Overview","score":{"value":"4.7","max":5}},\n'
            '    {"variant":"project_roadmap","title":"Project Roadmap","progress":{"value":76}},\n'
            '    {"variant":"financial_highlights","title":"Financial Highlights"},\n'
            '    {"variant":"employee_engagement","title":"Employee Engagement","score":{"value":89,"max":100}}\n'
            "  ]}\n\n"
            "process_flow — Numbered step cards connected by arrows (max 4 per row)\n"
            '  {"type":"process_flow","items":[{"title":"Sign Up","body":"Create account"},{"title":"Connect","body":"Link tools"}]}\n\n'
            "circular_flow — Editorial orbital layout: pastel bubbles around a thin orbit ring, vector line icons, a large center card, and optional side/footer callouts.\n"
            '  {"type":"circular_flow","center_label":"Better habits,\\nbetter you.","center_icon_name":"leaf",\n'
            '   "side_note":{"title":"Consistency is everything.","body":"Small steps every day lead to big results.","icon_name":"heart"},\n'
            '   "footer_panel":{"title":"Progress, not perfection.","body":"Focus on showing up for yourself every day.","icon_name":"mountain",\n'
            '     "steps":[{"label":"Start small","icon_name":"plant"},{"label":"Stay consistent","icon_name":"leaf"},{"label":"See the change","icon_name":"tree"}]},\n'
            '   "quote":"Take care of your body. It\'s the only place you have to live.","quote_icon_name":"heart",\n'
            '   "items":[{"title":"Hydrate","body":"Drink enough water throughout the day.","icon_name":"glass"},\n'
            '             {"title":"Mindfulness","body":"Take a few minutes to breathe and reset.","icon_name":"mindfulness"},\n'
            '             {"title":"Move","body":"Physical activity improves your energy.","icon_name":"shoe"}]}\n'
            "  Prefer icon_name for clean vector icons. Supported names include: glass, mindfulness, shoe, sun, book, sleep, leaf, heart, mountain, plant, tree.\n"
            "  center_icon / items[].icon / quote_icon may still be emoji when needed.\n\n"
            "staircase — Ascending colour steps, bottom-aligned\n"
            '  {"type":"staircase","items":[{"label":"Awareness","value":"1x"},{"label":"Interest","value":"2x"},{"label":"Decision"}]}\n\n'
            "pyramid — Layered trapezoid (narrowest top, widest bottom)\n"
            '  {"type":"pyramid","items":[{"label":"Vision","body":"Long-term"},{"label":"Strategy"},{"label":"Tactics"}]}\n\n'
            "snake_path — Serpentine numbered path (odd rows reverse direction)\n"
            '  {"type":"snake_path","items":[{"label":"Discover"},{"label":"Define"},{"label":"Design"},{"label":"Deliver"}]}\n\n'
            "bubble_chain — Horizontally linked circles, size proportional to value\n"
            '  {"type":"bubble_chain","items":[{"label":"Leads","value":500},{"label":"Qualified","value":200},{"label":"Closed","value":80}]}\n\n'
            "timeline — Horizontal timeline, alternating above/below labels\n"
            '  {"type":"timeline","items":[{"label":"Q1","date":"Jan 2026","body":"Launch"},{"label":"Q2","date":"Apr 2026"}]}\n\n'
            "venn — 2–3 overlapping Venn circles with optional intersection label\n"
            '  {"type":"venn","center_label":"Core","items":[{"label":"Engineering","items":["Fast"]},{"label":"Design","items":["Beautiful"]}]}\n\n'
            "comparison — Two-column VS comparison\n"
            '  {"type":"comparison","left":{"label":"Before","items":["Slow","Manual"]},"right":{"label":"After","items":["Fast","Automated"]}}\n\n'
            "swot — S/W/O/T 2×2 analysis grid\n"
            '  {"type":"swot","quadrants":[{"label":"Strengths","items":["Brand"]},{"label":"Weaknesses","items":["Churn"]},{"label":"Opportunities","items":["Markets"]},{"label":"Threats","items":["Rivals"]}]}\n\n'
            "matrix_2x2 — Generic 2×2 colour grid with optional axis labels\n"
            '  {"type":"matrix_2x2","x_label":"Impact","y_label":"Effort","cells":[{"label":"Quick Wins","body":"High impact, low effort"},{"label":"Projects","body":"High effort"},{"label":"Fill-ins","body":"Low value"},{"label":"Thankless","body":"Avoid"}]}\n\n'
            "quadrant_circle — Circle divided into 4 equal coloured sectors\n"
            '  {"type":"quadrant_circle","center_label":"Product","quadrants":[{"label":"Growth","value":"40%"},{"label":"Retention","value":"25%"},{"label":"Revenue","value":"20%"},{"label":"Cost","value":"15%"}]}\n\n'
            "card_grid — Flexible-column card grid with accent top stripe\n"
            '  {"type":"card_grid","cols":3,"items":[{"title":"Uptime","body":"99.98% in 30 days"},{"title":"Deploys","body":"42 this month"}]}\n\n'
            "pill_list — Horizontal colour pill steps with arrows\n"
            '  {"type":"pill_list","items":[{"label":"Intake","sub":"Day 1"},{"label":"Review","sub":"Day 3"},{"label":"Approve"}]}\n\n'
            "wheel — Segmented donut wheel (equal or value-proportional slices)\n"
            '  {"type":"wheel","equal":true,"center_label":"Teams","data":[{"label":"Eng"},{"label":"Design"},{"label":"Sales"},{"label":"Support"}]}\n\n'
            "━━ FULL EXAMPLE ━━\n"
            "{\n"
            '  "title": "Daily Ops Briefing",\n'
            '  "subtitle": "Engineering · Sales · Support",\n'
            '  "date": "Apr 16, 2026",\n'
            '  "theme": "midnight",\n'
            '  "sections": [\n'
            '    {"type":"kpi_row","items":[\n'
            '      {"label":"Messages","value":342,"change":"+12%","trend":"up"},\n'
            '      {"label":"Active users","value":18},\n'
            '      {"label":"Channels","value":9}\n'
            "    ]},\n"
            '    {"type":"divider"},\n'
            '    {"type":"bar_chart","title":"Channel Activity","data":[\n'
            '      {"label":"#engineering","value":120},\n'
            '      {"label":"#sales","value":80},\n'
            '      {"label":"#general","value":60}\n'
            "    ]},\n"
            '    {"type":"divider"},\n'
            '    {"type":"stories","title":"Top Stories","items":[\n'
            '      {"headline":"PR #412 merged","body":"Auth overhaul landed. Login latency -40%.","channel":"#engineering","author":"Alice"}\n'
            "    ]}\n"
            "  ]\n"
            "}\n\n"
            "Returns: svg_url, png_url (if cairosvg installed), svg_content (if small enough).\n"
            "Post the result to Slack: use internal_slack_post_blocks with an image block (when png_url/svg_url is available) "
            "or internal_slack_upload_file with svg_content (when S3 is not configured)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "spec": {
                    "type": "string",
                    "description": "Full infographic spec as a JSON string",
                },
                "output_format": {
                    "type": "string",
                    "enum": ["svg", "png", "both"],
                    "default": "both",
                    "description": "Output format. 'both' returns SVG + PNG (PNG needs cairosvg)",
                },
            },
            "required": ["spec"],
        },
        function=internal_generate_infographic,
        tool_category="diagram",
    )

    registry.register_tool(
        name="internal_generate_slack_infographic",
        description=(
            "Simplified infographic builder for Slack briefings — provide each section as a "
            "separate parameter instead of building the full spec manually.\n\n"
            "Use this when generating a CEO daily briefing or operations summary from Slack KB data.\n\n"
            "Workflow:\n"
            "1. Query Slack knowledge base for recent channel activity\n"
            "2. Aggregate: message counts per channel, top discussions, key decisions\n"
            "3. Call this tool with the aggregated data\n"
            "4. Post the returned png_url to Slack via internal_slack_send_message or blocks\n\n"
            "theme: daylight is the clean editorial preset for lifestyle/wellness infographics. "
            "Legacy aliases are accepted: dark → midnight, light → daylight, glass → aurora.\n\n"
            'kpis format:        \'[{"label":"Messages","value":342,"change":"+12%","trend":"up"}]\'\n'
            'bar_chart_data:     \'[{"label":"#engineering","value":120}]\'\n'
            'stories format:     \'[{"headline":"...","body":"...","channel":"#eng","author":"Alice"}]\'\n'
            "heatmap_data:       '[[0,2,0,...], ...]'  — 7 rows x 24 cols (optional)"
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Infographic headline, e.g. 'Daily Operations Briefing'",
                },
                "date": {
                    "type": "string",
                    "description": "Date shown in header badge, e.g. 'Apr 16, 2026'",
                },
                "kpis": {
                    "type": "string",
                    "description": "JSON array of KPI stat cards",
                },
                "bar_chart_title": {
                    "type": "string",
                    "description": "Title for the channel activity bar chart",
                },
                "bar_chart_data": {
                    "type": "string",
                    "description": "JSON array of bar chart entries [{label, value}]",
                },
                "stories": {
                    "type": "string",
                    "description": "JSON array of top story cards [{headline, body, channel?, author?}]",
                },
                "theme": {
                    "type": "string",
                    "enum": ["aurora", "midnight", "carbon", "sunset", "emerald", "daylight", "dark", "light", "glass"],
                    "default": "midnight",
                },
                "heatmap_data": {
                    "type": "string",
                    "description": "Optional 7x24 activity grid as JSON (7 day-rows, 24 hour-cols)",
                },
            },
            "required": ["title", "date", "kpis", "bar_chart_title", "bar_chart_data", "stories"],
        },
        function=internal_generate_slack_infographic,
        tool_category="diagram",
    )
