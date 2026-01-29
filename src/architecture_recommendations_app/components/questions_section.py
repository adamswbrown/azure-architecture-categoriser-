"""Questions section component for interactive clarification."""

import streamlit as st

from architecture_scorer.schema import ClarificationQuestion


def render_questions_section(questions: list[ClarificationQuestion]) -> dict | None:
    """Render the clarification questions section.

    Args:
        questions: List of clarification questions from the scorer

    Returns:
        Dictionary of user answers if submitted, None otherwise
    """
    st.subheader("Improve Recommendations")
    st.markdown("Answer these questions to improve recommendation accuracy:")

    answers = {}

    with st.container(border=True):
        for q in questions:
            # Build options list for selectbox
            options = ["-- Select --"] + [opt.value for opt in q.options]
            option_labels = {opt.value: opt.label for opt in q.options}

            # Format the question
            st.markdown(f"**{q.question_text}**")

            # Show current inference if available
            if q.current_inference:
                confidence_text = q.inference_confidence.value if q.inference_confidence else "unknown"
                st.caption(f"Current: {q.current_inference} ({confidence_text} confidence)")

            # Selectbox for answer
            selected = st.selectbox(
                q.question_text,
                options=options,
                format_func=lambda x: option_labels.get(x, x) if x != "-- Select --" else x,
                key=f"question_{q.question_id}",
                label_visibility="collapsed"
            )

            if selected != "-- Select --":
                answers[q.question_id] = selected

            # Show option description if selected
            if selected != "-- Select --":
                for opt in q.options:
                    if opt.value == selected and opt.description:
                        st.caption(f"_{opt.description}_")

            st.markdown("")  # Spacer

        # Submit button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(
                "Re-analyze with Answers",
                type="primary",
                use_container_width=True,
                disabled=len(answers) == 0
            ):
                if answers:
                    return answers

    return None
