"""Small presentation helpers shared by prototype pages."""

from __future__ import annotations

import streamlit as st


def page_caption(text: str) -> None:
    st.caption(text)


def source_badge(kind: str) -> None:
    config = {
        "HISTORICAL": ("真实历史数据", "blue"),
        "CONFIG": ("系统配置数据", "violet"),
        "SIMULATION": ("仿真生成数据", "orange"),
        "PROTOTYPE": ("阶段 3 原型", "gray"),
    }
    label, color = config.get(kind, (kind, "gray"))
    st.badge(label, color=color)


def section_header(title: str, caption: str | None = None, icon: str | None = None) -> None:
    st.subheader(title, icon=icon)
    if caption:
        st.caption(caption)


def stage_gate(title: str, body: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.write(body)
        st.caption("本页保留真实交互边界，不会用静态假数据冒充仿真结果。")


def empty_state(title: str, body: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.write(body)


def format_int(value: int | float) -> str:
    return f"{int(value):,}"


def format_float(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"
