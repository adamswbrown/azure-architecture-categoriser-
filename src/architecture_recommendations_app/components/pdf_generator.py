"""PDF report generator using reportlab."""

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_LEFT

from architecture_scorer.schema import ScoringResult, ArchitectureRecommendation


# Azure brand colors
AZURE_BLUE = HexColor('#0078D4')
AZURE_GREEN = HexColor('#107C10')
LIGHT_GRAY = HexColor('#F5F5F5')
DARK_GRAY = HexColor('#333333')


def generate_pdf_report(result: ScoringResult) -> bytes:
    """Generate a PDF report from scoring results.

    Args:
        result: The ScoringResult to format as PDF

    Returns:
        PDF file as bytes
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )

    # Build story (list of flowables)
    story = []
    styles = _get_custom_styles()

    # Title
    story.append(Paragraph("Azure Architecture Recommendations", styles['ReportTitle']))
    story.append(Spacer(1, 0.25 * inch))

    # Application info
    story.append(Paragraph(f"Application: {result.application_name}", styles['ReportHeading2']))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles['Normal']
    ))
    story.append(Spacer(1, 0.5 * inch))

    # Executive Summary section
    story.append(Paragraph("Executive Summary", styles['ReportHeading1']))
    story.append(Spacer(1, 0.1 * inch))

    summary = result.summary
    summary_data = [
        ["Primary Recommendation", summary.primary_recommendation or "None"],
        ["Confidence Level", summary.confidence_level],
        ["Total Recommendations", str(len(result.recommendations))],
        ["Architectures Evaluated", str(result.catalog_architecture_count)],
    ]

    summary_table = Table(summary_data, colWidths=[2.5 * inch, 4 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), LIGHT_GRAY),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.3 * inch))

    # Key drivers
    if summary.key_drivers:
        story.append(Paragraph("Key Drivers", styles['ReportHeading2']))
        for driver in summary.key_drivers[:5]:
            story.append(Paragraph(f"• {driver}", styles['BulletItem']))
        story.append(Spacer(1, 0.2 * inch))

    # Key risks
    if summary.key_risks:
        story.append(Paragraph("Key Considerations", styles['ReportHeading2']))
        for risk in summary.key_risks[:5]:
            story.append(Paragraph(f"• {risk}", styles['BulletItem']))
        story.append(Spacer(1, 0.3 * inch))

    # Recommendations
    story.append(Paragraph("Recommendations", styles['ReportHeading1']))
    story.append(Spacer(1, 0.1 * inch))

    for i, rec in enumerate(result.recommendations, 1):
        _add_recommendation_to_story(story, styles, rec, i)

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def _get_custom_styles():
    """Create custom paragraph styles for the report."""
    styles = getSampleStyleSheet()

    # Use unique names to avoid conflicts with built-in styles
    styles.add(ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        textColor=AZURE_BLUE,
        fontSize=24,
        spaceAfter=12
    ))

    styles.add(ParagraphStyle(
        'ReportHeading1',
        parent=styles['Heading1'],
        textColor=AZURE_BLUE,
        fontSize=16,
        spaceBefore=12,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        'ReportHeading2',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=8,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        'BulletItem',
        parent=styles['Normal'],
        leftIndent=20,
        spaceBefore=2,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        'RecommendationTitle',
        parent=styles['Heading2'],
        textColor=AZURE_GREEN,
        fontSize=13,
        spaceBefore=12,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#666666')
    ))

    return styles


def _add_recommendation_to_story(
    story: list,
    styles,
    rec: ArchitectureRecommendation,
    index: int
) -> None:
    """Add a recommendation section to the PDF story."""
    # Title with score
    title = f"{index}. {rec.name} ({rec.likelihood_score:.0f}% match)"
    story.append(Paragraph(title, styles['RecommendationTitle']))

    # Pattern and quality
    quality_label = rec.catalog_quality.value.replace('_', ' ').title()
    story.append(Paragraph(
        f"Pattern: {rec.pattern_name} | Quality: {quality_label}",
        styles['SmallText']
    ))

    story.append(Spacer(1, 0.1 * inch))

    # Try to include diagram image
    if rec.diagram_url:
        try:
            import requests
            response = requests.get(rec.diagram_url, timeout=10)
            if response.ok:
                img_buffer = BytesIO(response.content)
                # Smaller image size for cleaner PDF layout
                img = Image(img_buffer, width=4 * inch, height=2 * inch)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Spacer(1, 0.1 * inch))
        except Exception:
            # Skip image if it fails to load
            pass

    # Description (truncated)
    if rec.description:
        desc = rec.description[:500] + "..." if len(rec.description) > 500 else rec.description
        story.append(Paragraph(desc, styles['Normal']))

    story.append(Spacer(1, 0.1 * inch))

    # Why it fits
    if rec.fit_summary:
        story.append(Paragraph("Why it fits:", styles['ReportHeading2']))
        for fit in rec.fit_summary[:3]:
            story.append(Paragraph(f"• {fit}", styles['BulletItem']))

    # Potential challenges
    if rec.struggle_summary:
        story.append(Paragraph("Potential challenges:", styles['ReportHeading2']))
        for struggle in rec.struggle_summary[:3]:
            story.append(Paragraph(f"• {struggle}", styles['BulletItem']))

    # Core services
    if rec.core_services:
        services = ", ".join(rec.core_services[:6])
        story.append(Paragraph(f"Core Azure Services: {services}", styles['SmallText']))

    # Learn URL
    if rec.learn_url:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(f"Learn more: {rec.learn_url}", styles['SmallText']))

    story.append(Spacer(1, 0.3 * inch))
