from src.services.agents.internal_tools.infographic_tools import _normalize_infographic_theme
from src.services.diagrams.infographic_renderer import render_infographic


class TestInfographicRenderer:
    def test_render_daylight_circular_flow_editorial_layout(self):
        svg = render_infographic(
            {
                "title": "Small Habits, Big Change.",
                "subtitle": "Simple daily habits that improve your health, mood, and productivity.",
                "theme": "daylight",
                "sections": [
                    {
                        "type": "circular_flow",
                        "center_label": "Better habits,\nbetter you.",
                        "center_icon_name": "leaf",
                        "side_note": {
                            "title": "Consistency is everything.",
                            "body": "Small steps every day lead to big results.",
                            "icon_name": "heart",
                        },
                        "footer_panel": {
                            "title": "Progress, not perfection.",
                            "body": "Focus on showing up for yourself every day. You're growing.",
                            "icon_name": "mountain",
                            "steps": [
                                {"label": "Start small", "icon_name": "plant"},
                                {"label": "Stay consistent", "icon_name": "leaf"},
                                {"label": "See the change", "icon_name": "tree"},
                            ],
                        },
                        "quote": "Take care of your body. It's the only place you have to live.",
                        "quote_icon_name": "heart",
                        "items": [
                            {
                                "title": "Hydrate",
                                "body": "Drink enough water throughout the day to boost energy and focus.",
                                "icon_name": "glass",
                            },
                            {
                                "title": "Mindfulness",
                                "body": "Take a few minutes to breathe, reflect, and reset your mind.",
                                "icon_name": "mindfulness",
                            },
                            {
                                "title": "Move",
                                "body": "Physical activity improves your mood, energy, and sleep.",
                                "icon_name": "shoe",
                            },
                            {
                                "title": "Get Sunlight",
                                "body": "Natural light helps regulate your mood and sleep cycle.",
                                "icon_name": "sun",
                            },
                            {
                                "title": "Learn",
                                "body": "Keep your mind curious. Learning builds confidence and creativity.",
                                "icon_name": "book",
                            },
                            {
                                "title": "Sleep",
                                "body": "Quality sleep is the foundation for a better tomorrow.",
                                "icon_name": "sleep",
                            },
                        ],
                    }
                ],
            }
        )

        assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
        assert "Small Habits," in svg
        assert "Progress, not perfection." in svg
        assert "Consistency is everything." in svg
        assert "Take care of your body. It's the only place you have to live." in svg
        assert 'filter="url(#g_shadow_soft)"' in svg
        assert "g_center_card" in svg
        assert "g_blur_blob" in svg

    def test_render_sustainability_dashboard_reference_style(self):
        svg = render_infographic(
            {
                "title": "Sustainability Dashboard",
                "theme": "daylight",
                "sections": [
                    {
                        "type": "sustainability_dashboard",
                        "brand": "EcoFuture",
                        "report_label": "Sustainability Report 2024",
                        "title": "Building a Sustainable Tomorrow",
                        "subtitle": "Our 2024 highlights reflect our ongoing commitment to people, planet, and a better future for all.",
                        "cta_label": "Our Commitment",
                        "stats": [
                            {"label": "Trees Planted", "value": "1.2M", "change": "+18% vs 2023", "icon_name": "leaf"},
                            {"label": "Water Recycled", "value": "48%", "change": "+12% vs 2023", "icon_name": "glass"},
                            {"label": "Lives Impacted", "value": "25K+", "change": "+15% vs 2023", "icon_name": "user"},
                            {
                                "label": "Energy from Renewables",
                                "value": "34%",
                                "change": "+9% vs 2023",
                                "icon_name": "spark",
                            },
                        ],
                        "impacts": [
                            {
                                "title": "Environmental Stewardship",
                                "body": "Minimizing our environmental footprint",
                                "value": 92,
                                "icon_name": "leaf",
                            },
                            {
                                "title": "Social Responsibility",
                                "body": "Empowering communities and people",
                                "value": 87,
                                "icon_name": "user",
                            },
                            {
                                "title": "Ethical Governance",
                                "body": "Running our business with integrity",
                                "value": 90,
                                "icon_name": "shield",
                            },
                            {
                                "title": "Sustainable Innovation",
                                "body": "Driving innovation for a better tomorrow",
                                "value": 85,
                                "icon_name": "spark",
                            },
                        ],
                        "emissions": {
                            "title": "Emissions Reduced",
                            "subtitle": "Metric tons of CO2 equivalent",
                            "value": "18,754",
                            "change": "+20% vs 2023",
                            "filter_label": "Annual",
                            "series": [5000, 10800, 13200, 16700, 20700],
                            "x_labels": ["2020", "2021", "2022", "2023", "2024"],
                        },
                        "operations": {
                            "title": "Where We Operate",
                            "regions": [
                                {"label": "North America", "value": "35%"},
                                {"label": "Europe", "value": "28%"},
                                {"label": "Asia", "value": "22%"},
                                {"label": "Rest of World", "value": "15%"},
                            ],
                        },
                        "focus_areas": [
                            {
                                "title": "Climate Action",
                                "body": "Accelerating our journey to net zero emissions",
                                "icon_name": "leaf",
                            },
                            {
                                "title": "Water Positive",
                                "body": "Conserving and restoring water resources",
                                "icon_name": "glass",
                            },
                            {
                                "title": "Inclusive Growth",
                                "body": "Creating opportunities and empowering communities",
                                "icon_name": "user",
                            },
                            {
                                "title": "Responsible Innovation",
                                "body": "Designing solutions for a sustainable future",
                                "icon_name": "lightbulb",
                            },
                        ],
                        "recognitions": [
                            {
                                "title": "Sustainability Leader 2024",
                                "subtitle": "Global Green Awards",
                                "icon_name": "trophy",
                            },
                            {"title": "Top 50 Green Companies", "subtitle": "Corporate Knights", "icon_name": "trophy"},
                            {"title": "Best ESG Strategy", "subtitle": "Future Impact Awards", "icon_name": "trophy"},
                        ],
                        "quote": {
                            "text": "Sustainability is not just what we do, it's who we are.",
                            "author": "EcoFuture Team",
                        },
                        "principles": [
                            {"label": "Think Sustainably", "icon_name": "leaf"},
                            {"label": "Act Responsibly", "icon_name": "user"},
                            {"label": "Create Impact", "icon_name": "globe"},
                            {"label": "Inspire Change", "icon_name": "heart"},
                        ],
                    }
                ],
            }
        )

        assert "Building a" in svg
        assert "Sustainable" in svg
        assert "Tomorrow" in svg
        assert "Sustainability Report 2024" in svg
        assert "Emissions Reduced" in svg
        assert "Where We Operate" in svg
        assert "Sustainability is not just what we" in svg
        assert "do, it's who we are." in svg or "do, it&apos;s who we are." in svg

    def test_render_assessment_scorecard_reference_style(self):
        svg = render_infographic(
            {
                "title": "Assessment Scorecard",
                "theme": "daylight",
                "sections": [
                    {
                        "type": "assessment_scorecard",
                        "layout": "classic",
                        "badge": "Assessment Scorecard",
                        "title": "AI Readiness Assessment",
                        "subtitle": "A comprehensive evaluation of your organization's readiness to adopt and scale AI technologies.",
                        "facts": [
                            {"label": "Assessment Date", "value": "May 20, 2024", "icon_name": "calendar"},
                            {"label": "Assessed For", "value": "Acme Corporation", "icon_name": "user"},
                        ],
                        "score": 87,
                        "max_score": 100,
                        "status": "Excellent",
                        "score_note": "You're ahead of 78% of organizations in your industry.",
                        "delta": "+12",
                        "delta_caption": "vs. last assessment (Feb 20, 2024)",
                        "percentile_label": "Percentile Rank",
                        "percentile_value": "Top 22%",
                        "categories": [
                            {
                                "title": "Infrastructure",
                                "body": "Robustness and reliability of IT infrastructure",
                                "value": 92,
                                "status": "Excellent",
                                "icon_name": "server",
                            },
                            {
                                "title": "Security",
                                "body": "Security posture and data protection",
                                "value": 81,
                                "status": "Good",
                                "icon_name": "shield",
                            },
                            {
                                "title": "Automation",
                                "body": "Process automation and operational efficiency",
                                "value": 88,
                                "status": "Very Good",
                                "icon_name": "spark",
                            },
                            {
                                "title": "Scalability",
                                "body": "Ability to scale and adapt to growth",
                                "value": 90,
                                "status": "Excellent",
                                "icon_name": "layers",
                            },
                            {
                                "title": "Developer Experience",
                                "body": "Developer productivity and experience",
                                "value": 84,
                                "status": "Very Good",
                                "icon_name": "code",
                            },
                            {
                                "title": "AI Adoption",
                                "body": "AI tool adoption and integration",
                                "value": 79,
                                "status": "Good",
                                "icon_name": "mindfulness",
                            },
                        ],
                        "insights": [
                            {
                                "title": "Strong engineering foundation",
                                "body": "Your infrastructure and scalability scores are excellent and provide a solid base for AI initiatives.",
                                "icon_name": "heart",
                            },
                            {
                                "title": "Good scalability practices",
                                "body": "You're well-positioned to handle growth and increased workloads.",
                                "icon_name": "globe",
                            },
                            {
                                "title": "AI adoption improving steadily",
                                "body": "Your AI adoption score has improved by 15% since last assessment.",
                                "icon_name": "spark",
                            },
                            {
                                "title": "Security requires minor optimization",
                                "body": "Address a few gaps in data governance and access management.",
                                "icon_name": "shield",
                            },
                        ],
                        "recommendation": {
                            "title": "Focus on AI governance and workflow automation",
                            "body": "Implementing structured AI governance and expanding automation will help you reach enterprise-grade readiness and maximize ROI.",
                            "icon_name": "target",
                        },
                        "footer": {
                            "title": "Great work! You're building a future-ready organization.",
                            "body": "Keep up the momentum and continue improving.",
                            "note": "Next assessment recommended in 6 months",
                            "icon_name": "trophy",
                        },
                    }
                ],
            }
        )

        assert "AI Readiness" in svg
        assert "Assessment" in svg
        assert "OVERALL SCORE" in svg
        assert "Key Insights" in svg
        assert "Recommendation" in svg
        assert "Next assessment recommended in 6 months" in svg

    def test_render_assessment_scorecard_compact_certificate_style(self):
        svg = render_infographic(
            {
                "title": "AI Threat Certificate",
                "theme": "daylight",
                "sections": [
                    {
                        "type": "assessment_scorecard",
                        "badge": "AI Threat Certificate",
                        "title": "AI Threat Assessment",
                        "subtitle": "A compact replacement-risk certificate showing where AI tools are already displacing routine QA execution work.",
                        "facts": [
                            {"label": "Role", "value": "QA Engineer", "icon_name": "user"},
                            {"label": "Review Date", "value": "May 29, 2026", "icon_name": "calendar"},
                        ],
                        "score": 84,
                        "max_score": 100,
                        "status": "Critical",
                        "score_note": "This role is highly exposed to workflow automation and agentic testing tools.",
                        "risk_label": "High Risk",
                        "summary_body": "Routine execution-heavy tasks are already being handled by specialized AI QA platforms.",
                        "risk_items": [
                            {
                                "title": "Test case execution",
                                "value": 95,
                                "status": "Critical",
                                "body": "Repeatable scripted validation",
                            },
                            {
                                "title": "Regression testing",
                                "value": 93,
                                "status": "Critical",
                                "body": "Suite-based release coverage",
                            },
                            {
                                "title": "Bug reproduction",
                                "value": 82,
                                "status": "High",
                                "body": "Structured repro steps and logs",
                            },
                            {
                                "title": "Test documentation",
                                "value": 88,
                                "status": "Critical",
                                "body": "Standardized artifact generation",
                            },
                            {
                                "title": "Exploratory testing",
                                "value": 38,
                                "status": "Low",
                                "body": "Requires novel human intuition",
                            },
                            {
                                "title": "User empathy & edge cases",
                                "value": 29,
                                "status": "Low",
                                "body": "Context-rich product judgment",
                            },
                        ],
                        "key_insights": [
                            "Execution-heavy QA work is already being productized.",
                            "Highest threat sits in repeatable, rules-based testing loops.",
                            "Human value concentrates in ambiguity, empathy, and system judgment.",
                        ],
                        "recommendation": {
                            "title": "Move up-stack into product judgment and test strategy",
                            "body": "Prioritize exploratory testing, edge-case design, and cross-functional risk framing over repeatable execution work.",
                            "icon_name": "target",
                        },
                        "footer": {
                            "title": "Certificate summary",
                            "body": "Replacement pressure is concentrated in the most repeatable parts of the role.",
                            "note": "Reassess in 90 days",
                            "icon_name": "spark",
                        },
                        "risk_drivers": [
                            {"label": "Test execution", "value": 95, "status": "Critical"},
                            {"label": "Regression suites", "value": 93, "status": "Critical"},
                            {"label": "Documentation", "value": 88, "status": "Critical"},
                            {"label": "Bug triage", "value": 82, "status": "High"},
                            {"label": "Exploratory testing", "value": 38, "status": "Low"},
                        ],
                        "tools": [
                            "Testim",
                            "Mabl",
                            "Applitools",
                            "Copilot",
                            "Playwright",
                            "Launchable",
                        ],
                        "summary_cards": [
                            {"value": "84", "label": "Replacement Score"},
                            {"value": "Mabl", "label": "Top Threat"},
                            {"value": "1.6/10", "label": "Survival Rating"},
                        ],
                    }
                ],
            }
        )

        assert "AI Threat" in svg
        assert "Assessment" in svg
        assert "High Risk" in svg
        assert "Key Risk Drivers" in svg
        assert "AI Tools Already Doing It" in svg
        assert "Replacement Score" in svg
        assert "Launchable" in svg

    def test_render_assessment_scorecard_wraps_long_summary_label(self):
        svg = render_infographic(
            {
                "title": "AI Threat Certificate",
                "theme": "daylight",
                "sections": [
                    {
                        "type": "assessment_scorecard",
                        "title": "AI Threat Assessment",
                        "score": 18,
                        "max_score": 100,
                        "status": "Low Risk",
                        "risk_label": "Replacement Score 18%",
                        "risk_items": [
                            {"title": "Market research synthesis", "value": 75, "status": "High"},
                            {"title": "Memo / speech drafting", "value": 80, "status": "High"},
                        ],
                    }
                ],
            }
        )

        assert "Replacement" in svg
        assert "Score 18%" in svg

    def test_render_assessment_scorecard_hides_global_header_for_single_certificate(self):
        svg = render_infographic(
            {
                "title": "Professional example infographic",
                "subtitle": "This should not render as a separate infographic header.",
                "theme": "daylight",
                "sections": [
                    {
                        "type": "assessment_scorecard",
                        "title": "AI Threat Assessment",
                        "score": 18,
                        "max_score": 100,
                        "status": "Low Risk",
                        "risk_label": "Low Risk",
                        "risk_items": [
                            {"title": "Market research synthesis", "value": 75, "status": "High"},
                        ],
                    }
                ],
            }
        )

        assert "Professional example infographic" not in svg
        assert "AI Threat" in svg

    def test_render_showcase_dashboard_colorful_reference_style(self):
        svg = render_infographic(
            {
                "title": "Showcase Dashboard",
                "theme": "daylight",
                "sections": [
                    {
                        "type": "showcase_dashboard",
                        "cards": [
                            {
                                "variant": "business_performance",
                                "title": "Q2 Business Performance",
                                "subtitle": "Key insights from Apr – Jun 2024",
                                "overall": {"label": "Overall Performance", "value": "87%", "status": "Excellent"},
                                "stats": [
                                    {"label": "Revenue", "value": "$12.8M", "change": "↗ 18.6%", "icon_name": "spark"},
                                    {"label": "Orders", "value": "24.6K", "change": "↗ 22.4%", "icon_name": "layers"},
                                    {"label": "Customers", "value": "18.7K", "change": "↗ 16.3%", "icon_name": "user"},
                                    {
                                        "label": "Profit Margin",
                                        "value": "23.4%",
                                        "change": "↗ 5.7%",
                                        "icon_name": "target",
                                    },
                                ],
                                "trend": {
                                    "title": "Revenue Trend",
                                    "series": [4.5, 6.2, 6.0, 8.2, 8.0, 10.8],
                                    "x_labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                                    "badge": "$12.8M",
                                },
                                "channels": {
                                    "title": "Top Performing Channels",
                                    "data": [
                                        {"label": "Web", "value": 42, "color": "#5E5BFF"},
                                        {"label": "Mobile", "value": 28, "color": "#4BA8FF"},
                                        {"label": "Email", "value": 18, "color": "#30C975"},
                                        {"label": "Social", "value": 12, "color": "#7D4BFF"},
                                    ],
                                },
                                "takeaway": {
                                    "title": "Key Takeaway",
                                    "body": "Strong growth across all major metrics driven by increased demand and optimized campaigns.",
                                },
                                "next_steps": {
                                    "title": "Next Steps",
                                    "items": [
                                        "Invest in high-performing channels",
                                        "Optimize customer retention",
                                        "Expand product offerings",
                                    ],
                                },
                            },
                            {
                                "variant": "sustainability_impact",
                                "title": "Sustainability Impact Report 2024",
                                "subtitle": "Building today for a better tomorrow.",
                                "stats": [
                                    {
                                        "label": "Trees Planted",
                                        "value": "1.2M",
                                        "change": "↑ 20% vs 2023",
                                        "icon_name": "leaf",
                                    },
                                    {
                                        "label": "Water Recycled",
                                        "value": "48%",
                                        "change": "↑ 16% vs 2023",
                                        "icon_name": "glass",
                                    },
                                    {
                                        "label": "Lives Impacted",
                                        "value": "25K+",
                                        "change": "↑ 15% vs 2023",
                                        "icon_name": "user",
                                    },
                                    {
                                        "label": "Energy Renewables",
                                        "value": "34%",
                                        "change": "↑ 10% vs 2023",
                                        "icon_name": "spark",
                                    },
                                ],
                                "metric": {
                                    "title": "Carbon Footprint Reduced",
                                    "value": "19,876",
                                    "subtitle": "Metric tons of CO2 equivalent",
                                    "change": "↑ 19% vs 2023",
                                    "series": [6, 10, 13, 16, 20],
                                    "x_labels": ["2020", "2021", "2022", "2023", "2024"],
                                },
                                "focus_areas": [
                                    {
                                        "title": "Climate Action",
                                        "body": "Driving initiatives for a low-carbon future",
                                        "icon_name": "leaf",
                                    },
                                    {
                                        "title": "Circular Economy",
                                        "body": "Reducing waste and maximizing resources",
                                        "icon_name": "layers",
                                    },
                                    {
                                        "title": "Community Impact",
                                        "body": "Empowering people and strengthening communities",
                                        "icon_name": "user",
                                    },
                                ],
                                "quote": {
                                    "text": "Sustainability is not a goal, it's a commitment.",
                                    "author": "Our Planet, Our Future",
                                    "icon_name": "leaf",
                                },
                            },
                            {
                                "variant": "customer_satisfaction",
                                "title": "Customer Satisfaction Overview",
                                "subtitle": "2024 Report",
                                "score": {"value": "4.7", "max": 5, "label": "out of 5"},
                                "callout": {
                                    "title": "Your customers",
                                    "body": "love what you do!",
                                    "icon_name": "heart",
                                },
                                "stats": [
                                    {
                                        "label": "Happy Customers",
                                        "value": "92%",
                                        "change": "↑ 8% vs 2023",
                                        "icon_name": "heart",
                                    },
                                    {
                                        "label": "Feedbacks",
                                        "value": "1.3K",
                                        "change": "↑ 12% vs 2023",
                                        "icon_name": "chat",
                                    },
                                    {
                                        "label": "Avg. Response Time",
                                        "value": "2.4h",
                                        "change": "↓ 18% vs 2023",
                                        "icon_name": "calendar",
                                    },
                                    {
                                        "label": "Issue Resolution",
                                        "value": "98%",
                                        "change": "↑ 5% vs 2023",
                                        "icon_name": "shield",
                                    },
                                ],
                                "trend": {
                                    "title": "Satisfaction Trend",
                                    "series": [3.1, 3.6, 4.3, 4.4, 4.7, 4.7],
                                    "x_labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                                    "badge": "4.7",
                                },
                                "feedback": {
                                    "title": "Top Positive Feedback",
                                    "items": [
                                        '"Great product!"',
                                        '"Excellent support"',
                                        '"Easy to use"',
                                        '"Highly recommend"',
                                    ],
                                    "icon_name": "heart",
                                },
                            },
                            {
                                "variant": "project_roadmap",
                                "title": "Project Roadmap",
                                "subtitle": "Our journey to build the future",
                                "progress": {"label": "Progress", "value": 76},
                                "phases": [
                                    {
                                        "phase": "Phase 1",
                                        "title": "Research & Planning",
                                        "body": "Market Research Requirements Analysis",
                                        "status": "Completed",
                                        "icon_name": "lightbulb",
                                    },
                                    {
                                        "phase": "Phase 2",
                                        "title": "Design & Strategy",
                                        "body": "UI/UX Design Technical Architecture",
                                        "status": "Completed",
                                        "icon_name": "layers",
                                    },
                                    {
                                        "phase": "Phase 3",
                                        "title": "Development & Testing",
                                        "body": "Development Quality Testing",
                                        "status": "In Progress",
                                        "icon_name": "code",
                                    },
                                    {
                                        "phase": "Phase 4",
                                        "title": "Launch & Optimize",
                                        "body": "Product Launch Performance Optimization",
                                        "status": "Upcoming",
                                        "icon_name": "spark",
                                    },
                                ],
                                "milestones": {
                                    "title": "Key Milestones",
                                    "items": [
                                        {"label": "Jan", "title": "Project Kickoff", "icon_name": "lightbulb"},
                                        {"label": "Mar", "title": "Design System", "icon_name": "layers"},
                                        {"label": "May", "title": "Beta Release", "icon_name": "code"},
                                        {"label": "Jul", "title": "Official Launch", "icon_name": "spark"},
                                    ],
                                },
                            },
                            {
                                "variant": "financial_highlights",
                                "title": "Financial Highlights",
                                "subtitle": "FY 2024",
                                "series": {
                                    "labels": ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"],
                                    "bars": [
                                        {"label": "Revenue", "values": [18, 24, 26, 30], "color": "#4A6FFF"},
                                        {"label": "Profit", "values": [14, 13, 12, 17], "color": "#4FD17A"},
                                        {"label": "Expenses", "values": [7, 9, 8, 11], "color": "#FF5AA0"},
                                    ],
                                },
                                "metrics": [
                                    {
                                        "label": "Revenue",
                                        "value": "$52.4M",
                                        "change": "↑ 21.6% vs FY 2023",
                                        "icon_name": "spark",
                                    },
                                    {
                                        "label": "Profit",
                                        "value": "$14.8M",
                                        "change": "↑ 18.3% vs FY 2023",
                                        "icon_name": "leaf",
                                    },
                                    {
                                        "label": "Expenses",
                                        "value": "$27.6M",
                                        "change": "↑ 9.4% vs FY 2023",
                                        "icon_name": "target",
                                    },
                                ],
                                "kpis": [
                                    {
                                        "label": "Gross Margin",
                                        "value": "41.2%",
                                        "change": "↑ 2.7%",
                                        "icon_name": "layers",
                                    },
                                    {"label": "Net Margin", "value": "28.2%", "change": "↑ 3.1%", "icon_name": "leaf"},
                                    {
                                        "label": "Cash Flow",
                                        "value": "$11.2M",
                                        "change": "↑ 17.8%",
                                        "icon_name": "spark",
                                    },
                                    {"label": "ROI", "value": "32.6%", "change": "↑ 4.6%", "icon_name": "target"},
                                ],
                            },
                            {
                                "variant": "employee_engagement",
                                "title": "Employee Engagement",
                                "subtitle": "2024 Overview",
                                "score": {"label": "Engagement Score", "value": 89, "max": 100, "status": "Excellent"},
                                "dimensions": [
                                    {"label": "Company Culture", "value": "4.6 / 5"},
                                    {"label": "Work Satisfaction", "value": "4.4 / 5"},
                                    {"label": "Growth Opportunities", "value": "4.3 / 5"},
                                    {"label": "Employee Loyalty", "value": "4.7 / 5"},
                                ],
                                "stats": [
                                    {"label": "Participation Rate", "value": "93%", "change": "↑ 7% vs 2023"},
                                    {"label": "eNPS Score", "value": "+62", "change": "↑ 10 vs 2023"},
                                    {"label": "Training Hours", "value": "24.5K", "change": "↑ 15% vs 2023"},
                                    {"label": "Retention Rate", "value": "94%", "change": "↑ 6% vs 2023"},
                                ],
                                "quote": {
                                    "text": "Great teams are built on connection, purpose, and trust.",
                                    "cta": "Let's keep growing together!",
                                },
                            },
                        ],
                    }
                ],
            }
        )

        assert "Q2 Business" in svg
        assert "Sustainability" in svg
        assert "Impact Report" in svg
        assert "2024" in svg
        assert "Customer" in svg
        assert "Satisfaction" in svg
        assert "Project Roadmap" in svg
        assert "Financial Highlights" in svg
        assert "Employee Engagement" in svg


class TestInfographicThemeNormalization:
    def test_normalize_infographic_theme_maps_legacy_aliases(self):
        assert _normalize_infographic_theme("dark") == "midnight"
        assert _normalize_infographic_theme("light") == "daylight"
        assert _normalize_infographic_theme("glass") == "aurora"
        assert _normalize_infographic_theme("emerald") == "emerald"
