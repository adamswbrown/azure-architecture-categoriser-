"""UI components for the recommendations app."""

from architecture_recommendations_app.components.upload_section import render_upload_section
from architecture_recommendations_app.components.results_display import render_results
from architecture_recommendations_app.components.questions_section import render_questions_section
from architecture_recommendations_app.components.pdf_generator import generate_pdf_report

__all__ = [
    "render_upload_section",
    "render_results",
    "render_questions_section",
    "generate_pdf_report",
]
