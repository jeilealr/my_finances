"""Visualization helpers for the interactive dashboard."""

from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

INCOME_COLOR = "#157A5C"
EXPENSE_COLOR = "#B5273A"
NET_COLOR = "#264653"
ACCENT_COLOR = "#C47A3A"
TRANSFER_COLOR = "#7A8B99"
DONUT_HOLE_SIZE = 0.55
BANK_COLOR_MAP = {
    "santander": NET_COLOR,
    "revolut": INCOME_COLOR,
    "payback": EXPENSE_COLOR,
}
BACKGROUND_COLOR = "#FCFBF7"
PLOT_BACKGROUND_COLOR = "#FFFFFF"
FONT_COLOR = "#20323A"
MUTED_FONT_COLOR = "#5F6B73"
GRID_COLOR = "rgba(38, 70, 83, 0.16)"
BORDER_COLOR = "rgba(38, 70, 83, 0.14)"
CATEGORY_COLOR_MAP = {
    "ATM Withdrawal": "#7A8B99",
    "Bank Fees": "#B56576",
    "Blocked Account": "#7F1D5A",
    "Card Repayment": "#C17767",
    "Colombia Transfer": "#2F6F95",
    "Dance": "#C8553D",
    "Electricity": "#4D908E",
    "Fitness": "#43AA8B",
    "Grocery Shopping": "#2A9D8F",
    "Grocery": "#2A9D8F",
    "Housing & Utilities": "#46656F",
    "Income": "#1F9D78",
    "Entertainment": "#E07A5F",
    "Pharmacy": "#F28482",
    "Interest Income": "#55A630",
    "Internal Transfer": "#577590",
    "Investment Fees": "#B08968",
    "Investments": "#6A994E",
    "Other": "#B6AD90",
    "Phone & Internet": "#8E7DBE",
    "Rent": "#E76F51",
    "Restaurants & Delivery": "#F4A261",
    "Retail & Online Shopping": "#9C6644",
    "Salary": "#1D7874",
    "Savings": "#277DA1",
    "Shopping": "#9C6644",
    "Transport": "#BC5090",
    "Travel": "#577590",
    "Travel & Holidays": "#577590",
    "Utilities": "#5F0F40",
    "Remaining Paycheck": "#B7C8A5",
    "Other Spending Groups": "#B6AD90",
}
NET_WORTH_COLORS = {
    "Santander Account": "#2F6F73",
    "Revolut Account": "#75A99C",
    "Revolut Savings": "#2E5EAA",
    "Blocked Account": "#C58B4C",
    "Payback Known Debt": "#C4455C",
    "Investment": "#8A6F2A",
    "Total Net Worth": "#20323A",
    "Tracked Wealth": "#E8903A",
}


def _currency_values(dataframe: pd.DataFrame) -> list[str]:
    """Return sorted non-empty currency labels for chart faceting."""
    if "currency" not in dataframe.columns or dataframe.empty:
        return []
    return sorted(
        dataframe["currency"].fillna("Unknown").replace("", "Unknown").unique()
    )


def _category_color_map(categories: pd.Series | list[str]) -> dict[str, str]:
    """Return a stable color map for the categories currently in view."""
    labels = pd.Series(categories).dropna().astype(str).unique().tolist()
    fallback_palette = px.colors.qualitative.Safe + px.colors.qualitative.Set3
    color_map: dict[str, str] = {}
    for index, label in enumerate(sorted(labels)):
        color_map[label] = CATEGORY_COLOR_MAP.get(
            label,
            fallback_palette[index % len(fallback_palette)],
        )
    return color_map


def _empty_figure(message: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 16, "color": FONT_COLOR},
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return _apply_dashboard_theme(figure)


def _format_compact_amount(value: float) -> str:
    """Return a compact amount for annotations."""
    absolute_value = abs(value)
    if absolute_value >= 1_000_000:
        formatted = f"{value / 1_000_000:.1f}M"
        return formatted.replace(".0M", "M")
    if absolute_value >= 1_000:
        formatted = f"{value / 1_000:.1f}k"
        return formatted.replace(".0k", "k")
    if absolute_value >= 100:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _monthly_axis_range(monthly_summary: pd.DataFrame) -> list[pd.Timestamp] | None:
    """Return a date range that keeps month ticks inside the visible period."""
    if monthly_summary.empty or "month" not in monthly_summary.columns:
        return None

    start = monthly_summary["month"].min()
    end = monthly_summary["month"].max() + pd.offsets.MonthBegin(1)
    return [start, end]


def _movement_annotation_data(
    extra_transaction_summary: pd.DataFrame | None,
    *,
    currency: str,
) -> pd.DataFrame:
    """Build one compact monthly annotation per month and currency."""
    if extra_transaction_summary is None or extra_transaction_summary.empty:
        return pd.DataFrame(columns=["month", "text", "hover_text"])

    extra_data = extra_transaction_summary.loc[
        extra_transaction_summary["currency"].eq(currency)
    ].copy()
    if extra_data.empty:
        return pd.DataFrame(columns=["month", "text", "hover_text"])

    if {"extra_amount", "detail_text"}.issubset(extra_data.columns):
        extra_data["text"] = extra_data["extra_amount"].map(
            lambda value: f"Extra<br>{_format_compact_amount(value)}"
        )
        extra_data["hover_text"] = extra_data.apply(
            lambda row: (
                f"<b>Extra transactions {row['month_label']}</b>"
                f"<br>Total: {row['extra_amount']:,.2f} {row['currency']}"
                f"<br><br>{row['detail_text']}"
            ),
            axis=1,
        )
        return extra_data.loc[:, ["month", "text", "hover_text"]]

    fallback = (
        extra_data.groupby(["month", "month_label"], dropna=False)["movement_amount"]
        .sum()
        .reset_index()
    )
    fallback["text"] = fallback["movement_amount"].map(
        lambda value: f"Extra<br>{_format_compact_amount(value)}"
    )
    fallback["hover_text"] = fallback["text"]
    return fallback.loc[:, ["month", "text", "hover_text"]]


def _apply_dashboard_theme(
    figure: go.Figure, *, height: int | None = None
) -> go.Figure:
    """Apply a consistent high-contrast theme to dashboard charts."""
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor=PLOT_BACKGROUND_COLOR,
        plot_bgcolor=PLOT_BACKGROUND_COLOR,
        font={
            "family": "Avenir Next, Avenir, Segoe UI, Helvetica Neue, sans-serif",
            "color": FONT_COLOR,
            "size": 13,
        },
        hoverlabel={
            "bgcolor": "#FFFDF9",
            "bordercolor": BORDER_COLOR,
            "font": {"color": FONT_COLOR},
        },
        legend={
            "bgcolor": "rgba(255, 255, 255, 0.9)",
            "bordercolor": BORDER_COLOR,
            "borderwidth": 1,
            "font": {"color": FONT_COLOR},
            "title": {"font": {"color": FONT_COLOR}},
        },
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )
    if height is not None:
        figure.update_layout(height=height)

    figure.update_annotations(font={"color": FONT_COLOR, "size": 15})
    figure.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=BORDER_COLOR,
        tickcolor=BORDER_COLOR,
        tickfont={"color": MUTED_FONT_COLOR, "size": 12},
        title_font={"color": MUTED_FONT_COLOR, "size": 13},
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor=GRID_COLOR,
        gridwidth=1,
        zeroline=False,
        linecolor=BORDER_COLOR,
        tickcolor=BORDER_COLOR,
        tickfont={"color": MUTED_FONT_COLOR, "size": 12},
        title_font={"color": MUTED_FONT_COLOR, "size": 13},
    )
    return figure


def monthly_cashflow_chart(
    monthly_summary: pd.DataFrame,
    extra_transaction_summary: pd.DataFrame | None = None,
) -> go.Figure:
    """Return a combined income/expense/net chart with extra-transaction labels."""
    if monthly_summary.empty:
        return _empty_figure("No monthly data available for the current filters.")

    currencies = _currency_values(monthly_summary)
    figure = make_subplots(
        rows=max(1, len(currencies)),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=currencies or ["Monthly Cashflow"],
        specs=[[{"secondary_y": True}] for _ in range(max(1, len(currencies)))],
    )

    for row_index, currency in enumerate(currencies or [""], start=1):
        if currency:
            plot_data = monthly_summary.loc[monthly_summary["currency"].eq(currency)]
        else:
            plot_data = monthly_summary

        custom_data = plot_data[["month_label"]]
        show_legend = row_index == 1
        figure.add_bar(
            x=plot_data["month"],
            y=plot_data["income"],
            name="Income",
            customdata=custom_data,
            xperiod="M1",
            xperiodalignment="middle",
            marker_color=INCOME_COLOR,
            text="Income",
            textposition="inside",
            textfont={"color": "#FFFFFF", "size": 11},
            hovertemplate=("Month=%{customdata[0]}<br>Income=%{y:.2f}<extra></extra>"),
            row=row_index,
            col=1,
            secondary_y=False,
            showlegend=show_legend,
        )
        figure.add_bar(
            x=plot_data["month"],
            y=plot_data["expenses"],
            name="Expenses",
            customdata=custom_data,
            xperiod="M1",
            xperiodalignment="middle",
            marker_color=EXPENSE_COLOR,
            text="Expenses",
            textposition="inside",
            textfont={"color": "#FFFFFF", "size": 11},
            hovertemplate=(
                "Month=%{customdata[0]}<br>Expenses=%{y:.2f}<extra></extra>"
            ),
            row=row_index,
            col=1,
            secondary_y=False,
            showlegend=show_legend,
        )
        figure.add_scatter(
            x=plot_data["month"],
            y=plot_data["net"],
            name="Net",
            mode="lines+markers",
            customdata=custom_data,
            xperiod="M1",
            xperiodalignment="middle",
            line={"color": NET_COLOR, "width": 3},
            hovertemplate="Month=%{customdata[0]}<br>Net=%{y:.2f}<extra></extra>",
            row=row_index,
            col=1,
            secondary_y=True,
            showlegend=show_legend,
        )
        movement_data = _movement_annotation_data(
            extra_transaction_summary,
            currency=currency,
        )
        if not movement_data.empty:
            primary_max = plot_data[["income", "expenses"]].max(axis=1).max() or 1.0
            base_annotation_y = primary_max * 1.12
            movement_data = movement_data.sort_values("month").reset_index(drop=True)
            movement_y = [
                base_annotation_y + (primary_max * 0.12 * (index % 2))
                for index in range(len(movement_data))
            ]
            figure.add_scatter(
                x=movement_data["month"],
                y=movement_y,
                text=movement_data["text"],
                customdata=movement_data[["hover_text"]],
                mode="markers+text",
                xperiod="M1",
                xperiodalignment="middle",
                textposition="top center",
                textfont={"color": FONT_COLOR, "size": 11},
                marker={
                    "size": 10,
                    "color": ACCENT_COLOR,
                    "line": {"color": "#FFFFFF", "width": 1.4},
                    "opacity": 0.96,
                },
                hovertemplate="%{customdata[0]}<extra></extra>",
                showlegend=False,
                cliponaxis=False,
                row=row_index,
                col=1,
                secondary_y=False,
            )
            figure.update_yaxes(
                range=[0, primary_max * 1.48],
                row=row_index,
                col=1,
                secondary_y=False,
            )
        yaxis_title = f"Amount ({currency})" if currency else "Amount"
        figure.update_yaxes(
            title_text=yaxis_title,
            row=row_index,
            col=1,
            secondary_y=False,
        )
        figure.update_yaxes(
            title_text=f"Net ({currency})" if currency else "Net",
            row=row_index,
            col=1,
            secondary_y=True,
            showgrid=False,
        )

    figure.update_layout(
        barmode="group",
        legend_title_text="",
    )
    figure = _apply_dashboard_theme(
        figure,
        height=max(380, 330 * max(1, len(currencies))),
    )
    for row_index, currency in enumerate(currencies or [""], start=1):
        figure.update_xaxes(
            type="date",
            dtick="M1",
            tickformat="%b<br>%Y",
            ticklabelmode="period",
            range=_monthly_axis_range(monthly_summary),
            row=row_index,
            col=1,
        )
        figure.update_yaxes(
            title_text=f"Amount ({currency})" if currency else "Amount",
            row=row_index,
            col=1,
            secondary_y=False,
        )
        figure.update_yaxes(
            title_text=f"Net ({currency})" if currency else "Net",
            row=row_index,
            col=1,
            secondary_y=True,
            showgrid=False,
        )
    return figure


def budget_monthly_chart(monthly_budget: pd.DataFrame) -> go.Figure:
    """Return salary, fixed commitments, and money-left trends by month."""
    if monthly_budget.empty:
        return _empty_figure("No budget data is available for the current filters.")

    currencies = _currency_values(monthly_budget)
    figure = make_subplots(
        rows=max(1, len(currencies)),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=currencies or ["Budget"],
        specs=[[{"secondary_y": True}] for _ in range(max(1, len(currencies)))],
    )

    for row_index, currency in enumerate(currencies or [""], start=1):
        if currency:
            plot_data = monthly_budget.loc[monthly_budget["currency"].eq(currency)]
        else:
            plot_data = monthly_budget

        custom_data = plot_data[["month_label"]]
        show_legend = row_index == 1
        figure.add_bar(
            x=plot_data["month"],
            y=plot_data["salary"],
            name="Salary",
            customdata=custom_data,
            xperiod="M1",
            xperiodalignment="middle",
            marker_color=INCOME_COLOR,
            hovertemplate="Month=%{customdata[0]}<br>Salary=%{y:.2f}<extra></extra>",
            row=row_index,
            col=1,
            secondary_y=False,
            showlegend=show_legend,
        )
        figure.add_bar(
            x=plot_data["month"],
            y=plot_data["fixed_commitments"],
            name="Fixed Commitments",
            customdata=custom_data,
            xperiod="M1",
            xperiodalignment="middle",
            marker_color=EXPENSE_COLOR,
            hovertemplate=(
                "Month=%{customdata[0]}<br>Fixed Commitments=%{y:.2f}<extra></extra>"
            ),
            row=row_index,
            col=1,
            secondary_y=False,
            showlegend=show_legend,
        )
        figure.add_scatter(
            x=plot_data["month"],
            y=plot_data["money_left"],
            name="Money Left",
            mode="lines+markers",
            customdata=custom_data,
            xperiod="M1",
            xperiodalignment="middle",
            line={"color": NET_COLOR, "width": 3},
            marker={"size": 7},
            hovertemplate="Month=%{customdata[0]}<br>Money Left=%{y:.2f}<extra></extra>",
            row=row_index,
            col=1,
            secondary_y=True,
            showlegend=show_legend,
        )
        figure.update_yaxes(
            title_text=f"Amount ({currency})" if currency else "Amount",
            row=row_index,
            col=1,
            secondary_y=False,
        )
        figure.update_yaxes(
            title_text=f"Money Left ({currency})" if currency else "Money Left",
            row=row_index,
            col=1,
            secondary_y=True,
            showgrid=False,
        )

    figure.update_layout(
        barmode="group",
        legend_title_text="",
    )
    figure = _apply_dashboard_theme(
        figure,
        height=max(380, 330 * max(1, len(currencies))),
    )
    for row_index, _currency in enumerate(currencies or [""], start=1):
        axis_name = "xaxis" if row_index == 1 else f"xaxis{row_index}"
        figure.layout[axis_name].update(dtick="M1", tickformat="%b<br>%Y")
    return figure


def paycheck_allocation_chart(allocation_data: pd.DataFrame) -> go.Figure:
    """Return a donut chart for selected-month paycheck allocation."""
    if allocation_data.empty:
        return _empty_figure("No paycheck allocation is available for this month.")

    plot_data = allocation_data.loc[allocation_data["amount"].gt(0)].copy()
    if plot_data.empty:
        return _empty_figure("No positive paycheck allocation is available.")

    color_map = _category_color_map(plot_data["bucket"])
    figure = go.Figure(
        data=[
            go.Pie(
                labels=plot_data["bucket"],
                values=plot_data["amount"],
                hole=DONUT_HOLE_SIZE,
                sort=False,
                marker={
                    "colors": [color_map[label] for label in plot_data["bucket"]]
                },
                texttemplate="%{label}<br>%{value:,.0f}<br>%{percent}",
                textposition="inside",
                hovertemplate="%{label}<br>%{value:,.2f}<br>%{percent}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        showlegend=True,
        legend_title_text="Allocation",
    )
    return _apply_dashboard_theme(figure, height=420)


def net_worth_chart(net_worth_summary: pd.DataFrame) -> go.Figure:
    """Return a split net-worth chart with component bars and total line."""
    if net_worth_summary.empty:
        return _empty_figure("No net-worth snapshots are available.")

    figure = go.Figure()
    component_columns = [
        ("Santander Account", "santander_cash"),
        ("Revolut Account", "revolut_cash"),
        ("Revolut Savings", "revolut_savings"),
        ("Blocked Account", "blocked_account"),
        ("Payback Known Debt", "payback_debt"),
    ]
    for label, column in component_columns:
        values = (
            -net_worth_summary[column]
            if label == "Payback Known Debt"
            else net_worth_summary[column]
        )
        figure.add_bar(
            x=net_worth_summary["month"],
            y=values,
            name=label,
            marker_color=NET_WORTH_COLORS[label],
            customdata=net_worth_summary[["month_label", "currency"]],
            xperiod="M1",
            xperiodalignment="middle",
            hovertemplate=(
                "Month=%{customdata[0]}<br>"
                f"{label}=%{{y:,.2f}} %{{customdata[1]}}<extra></extra>"
            ),
        )

    figure.add_scatter(
        x=net_worth_summary["month"],
        y=net_worth_summary["total_net_worth"],
        name="Total Net Worth",
        mode="lines+markers",
        line={"color": NET_WORTH_COLORS["Total Net Worth"], "width": 4},
        marker={
            "size": 8,
            "color": NET_WORTH_COLORS["Total Net Worth"],
            "line": {"color": "#FFFFFF", "width": 1.2},
        },
        customdata=net_worth_summary[["month_label", "currency"]],
        xperiod="M1",
        xperiodalignment="middle",
        hovertemplate=(
            "Month=%{customdata[0]}<br>"
            "Total Net Worth=%{y:,.2f} %{customdata[1]}<extra></extra>"
        ),
    )
    if "tracked_wealth" in net_worth_summary.columns:
        figure.add_scatter(
            x=net_worth_summary["month"],
            y=net_worth_summary["tracked_wealth"],
            name="Tracked Wealth",
            mode="lines+markers",
            line={"color": NET_WORTH_COLORS["Tracked Wealth"], "width": 3.4},
            marker={
                "size": 8,
                "color": NET_WORTH_COLORS["Tracked Wealth"],
                "line": {"color": "#FFFFFF", "width": 1.1},
            },
            customdata=net_worth_summary[["month_label", "currency"]],
            xperiod="M1",
            xperiodalignment="middle",
            hovertemplate=(
                "Month=%{customdata[0]}<br>"
                "Tracked Wealth=%{y:,.2f} %{customdata[1]}<extra></extra>"
            ),
        )
    investment_column = (
        "investment_market_value"
        if "investment_market_value" in net_worth_summary.columns
        else "investments"
    )
    investment_customdata_columns = [
        "month_label",
        "currency",
        "investment_cost_basis",
        "investment_gain_loss",
    ]
    if not set(investment_customdata_columns).issubset(net_worth_summary.columns):
        investment_customdata_columns = ["month_label", "currency"]
        investment_hover = (
            "Month=%{customdata[0]}<br>"
            "Investment=%{y:,.2f} %{customdata[1]}<extra></extra>"
        )
    else:
        investment_hover = (
            "Month=%{customdata[0]}<br>"
            "Investment=%{y:,.2f} %{customdata[1]}<br>"
            "Cost Basis=%{customdata[2]:,.2f} %{customdata[1]}<br>"
            "Gain/Loss=%{customdata[3]:,.2f} %{customdata[1]}<extra></extra>"
        )
    figure.add_scatter(
        x=net_worth_summary["month"],
        y=net_worth_summary[investment_column],
        name="Investment",
        mode="lines+markers",
        line={"color": NET_WORTH_COLORS["Investment"], "dash": "dot", "width": 3},
        marker={
            "size": 7,
            "color": NET_WORTH_COLORS["Investment"],
            "line": {"color": "#FFFFFF", "width": 1},
        },
        customdata=net_worth_summary[investment_customdata_columns],
        xperiod="M1",
        xperiodalignment="middle",
        hovertemplate=investment_hover,
    )
    figure.update_layout(
        barmode="relative",
        xaxis_title="Month",
        yaxis_title="Amount",
        legend_title_text="Component",
    )
    figure = _apply_dashboard_theme(figure, height=430)
    figure.update_xaxes(
        type="date",
        dtick="M1",
        tickformat="%b<br>%Y",
        ticklabelmode="period",
        range=_monthly_axis_range(net_worth_summary),
    )
    return figure


def payback_debt_chart(payback_debt_summary: pd.DataFrame) -> go.Figure:
    """Return monthly Payback purchases, credits, and outstanding debt."""
    if payback_debt_summary.empty:
        return _empty_figure("No Payback debt data is available.")

    figure = make_subplots(specs=[[{"secondary_y": True}]])
    custom_data = payback_debt_summary[["month_label", "currency"]]
    figure.add_bar(
        x=payback_debt_summary["month"],
        y=payback_debt_summary["purchases"],
        name="Purchases",
        marker_color=EXPENSE_COLOR,
        customdata=custom_data,
        xperiod="M1",
        xperiodalignment="middle",
        hovertemplate=(
            "Month=%{customdata[0]}<br>Purchases=%{y:,.2f} "
            "%{customdata[1]}<extra></extra>"
        ),
        secondary_y=False,
    )
    figure.add_bar(
        x=payback_debt_summary["month"],
        y=payback_debt_summary["repayments"],
        name="Credits / Repayments",
        marker_color=INCOME_COLOR,
        customdata=custom_data,
        xperiod="M1",
        xperiodalignment="middle",
        hovertemplate=(
            "Month=%{customdata[0]}<br>Credits / Repayments=%{y:,.2f} "
            "%{customdata[1]}<extra></extra>"
        ),
        secondary_y=False,
    )
    figure.add_scatter(
        x=payback_debt_summary["month"],
        y=payback_debt_summary["outstanding_debt"],
        name="Outstanding Debt",
        mode="lines+markers",
        line={"color": NET_COLOR, "width": 3},
        customdata=custom_data,
        xperiod="M1",
        xperiodalignment="middle",
        hovertemplate=(
            "Month=%{customdata[0]}<br>Outstanding=%{y:,.2f} "
            "%{customdata[1]}<extra></extra>"
        ),
        secondary_y=True,
    )
    figure.update_layout(
        barmode="group",
        xaxis_title="Month",
        legend_title_text="",
    )
    figure = _apply_dashboard_theme(figure, height=430)
    figure.update_xaxes(
        type="date",
        dtick="M1",
        tickformat="%b<br>%Y",
        ticklabelmode="period",
        range=_monthly_axis_range(payback_debt_summary),
    )
    figure.update_yaxes(title_text="Monthly Activity", secondary_y=False)
    figure.update_yaxes(title_text="Outstanding Debt", secondary_y=True, showgrid=False)
    return figure


def category_bar_chart(category_summary: pd.DataFrame) -> go.Figure:
    """Return a horizontal category comparison chart."""
    if category_summary.empty:
        return _empty_figure("No expense categories match the current filters.")

    plot_data = category_summary.sort_values(["currency", "expenses"], ascending=True)
    color_map = _category_color_map(plot_data["category"])
    figure = px.bar(
        plot_data,
        x="expenses",
        y="category",
        orientation="h",
        color="category",
        text_auto=".2s",
        facet_col="currency" if len(_currency_values(plot_data)) > 1 else None,
        facet_col_wrap=2,
        color_discrete_map=color_map,
    )
    figure.update_traces(hovertemplate="%{y}<br>Expenses=%{x:.2f}<extra></extra>")
    figure.update_traces(
        textfont={"color": FONT_COLOR, "size": 12},
        marker_line_color="rgba(255, 255, 255, 0.45)",
        marker_line_width=1,
    )
    figure.update_layout(
        showlegend=False,
        xaxis_title="Expenses",
        yaxis_title="",
    )
    return _apply_dashboard_theme(figure)


def category_donut_chart(category_summary: pd.DataFrame) -> go.Figure:
    """Return a donut chart showing category distribution."""
    if category_summary.empty:
        return _empty_figure("No expense categories available.")

    currencies = _currency_values(category_summary)
    columns = min(2, max(1, len(currencies)))
    rows = math.ceil(max(1, len(currencies)) / columns)
    figure = make_subplots(
        rows=rows,
        cols=columns,
        specs=[[{"type": "domain"} for _ in range(columns)] for _ in range(rows)],
        subplot_titles=currencies or ["Expenses"],
    )

    for index, currency in enumerate(currencies or [""], start=1):
        row = ((index - 1) // columns) + 1
        col = ((index - 1) % columns) + 1
        if currency:
            plot_data = category_summary.loc[
                category_summary["currency"].eq(currency)
            ].copy()
        else:
            plot_data = category_summary.copy()

        if len(plot_data) > 6:
            top = plot_data.head(6)
            other_total = plot_data.iloc[6:]["expenses"].sum()
            plot_data = pd.concat(
                [
                    top,
                    pd.DataFrame(
                        {
                            "currency": [currency or ""],
                            "category": ["Other"],
                            "expenses": [other_total],
                        }
                    ),
                ],
                ignore_index=True,
            )

        color_map = _category_color_map(plot_data["category"])
        figure.add_trace(
            go.Pie(
                labels=plot_data["category"],
                values=plot_data["expenses"],
                hole=DONUT_HOLE_SIZE,
                sort=False,
                marker={
                    "colors": [color_map[label] for label in plot_data["category"]]
                },
                hovertemplate=(
                    "%{label}<br>Expenses=%{value:.2f}"
                    "<br>Share=%{percent}<extra></extra>"
                ),
            ),
            row=row,
            col=col,
        )

    figure.update_layout(
        legend_title_text="Category",
        height=max(360, 320 * rows),
    )
    figure.update_traces(textfont={"color": FONT_COLOR})
    return _apply_dashboard_theme(figure)


def report_expense_pie_chart(monthly_grouped_expenses: pd.DataFrame) -> go.Figure:
    """Return a Reports pie chart for grouped expenses in one month."""
    if monthly_grouped_expenses.empty:
        return _empty_figure("No grouped expenses are available for this month.")

    currencies = _currency_values(monthly_grouped_expenses)
    columns = min(2, max(1, len(currencies)))
    rows = math.ceil(max(1, len(currencies)) / columns)
    figure = make_subplots(
        rows=rows,
        cols=columns,
        specs=[[{"type": "domain"} for _ in range(columns)] for _ in range(rows)],
        subplot_titles=currencies or ["Expenses"],
    )

    for index, currency in enumerate(currencies or [""], start=1):
        row = ((index - 1) // columns) + 1
        col = ((index - 1) % columns) + 1
        if currency:
            plot_data = monthly_grouped_expenses.loc[
                monthly_grouped_expenses["currency"].eq(currency)
            ].copy()
        else:
            plot_data = monthly_grouped_expenses.copy()

        color_map = _category_color_map(plot_data["report_group"])
        figure.add_trace(
            go.Pie(
                labels=plot_data["report_group"],
                values=plot_data["expenses"],
                hole=DONUT_HOLE_SIZE,
                sort=False,
                marker={
                    "colors": [
                        color_map[label] for label in plot_data["report_group"]
                    ],
                    "line": {"color": "#FFFFFF", "width": 1.4},
                },
                hovertemplate=(
                    "%{label}<br>Expenses=%{value:,.2f}"
                    "<br>Share=%{percent}<extra></extra>"
                ),
            ),
            row=row,
            col=col,
        )

    figure.update_layout(
        legend_title_text="Expense Group",
        height=max(390, 340 * rows),
    )
    figure.update_traces(textfont={"color": FONT_COLOR, "size": 13})
    return _apply_dashboard_theme(figure)


def monthly_grouped_expense_chart(grouped_expenses: pd.DataFrame) -> go.Figure:
    """Return a month-by-month stacked chart for grouped report expenses."""
    if grouped_expenses.empty:
        return _empty_figure("No grouped monthly expenses are available.")

    plot_data = grouped_expenses.sort_values(["currency", "month", "report_group"])
    color_map = _category_color_map(plot_data["report_group"])
    figure = px.bar(
        plot_data,
        x="month_label",
        y="expenses",
        color="report_group",
        barmode="stack",
        facet_col="currency" if len(_currency_values(plot_data)) > 1 else None,
        facet_col_wrap=2,
        color_discrete_map=color_map,
        hover_data={"transactions": True},
    )
    figure.update_traces(
        marker_line_color="rgba(255, 255, 255, 0.42)",
        marker_line_width=0.9,
        hovertemplate=(
            "%{x}<br>%{fullData.name}: %{y:,.2f}"
            "<br>Transactions=%{customdata[0]}<extra></extra>"
        ),
    )
    figure.update_layout(
        xaxis_title="Month",
        yaxis_title="Expenses",
        legend_title_text="Expense Group",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )
    return _apply_dashboard_theme(figure)


def report_group_component_chart(component_summary: pd.DataFrame) -> go.Figure:
    """Return monthly category components for one selected Reports group."""
    if component_summary.empty:
        return _empty_figure("No category components are available for this group.")

    plot_data = component_summary.sort_values(["currency", "month", "category"])
    color_map = _category_color_map(plot_data["category"])
    figure = px.bar(
        plot_data,
        x="month_label",
        y="expenses",
        color="category",
        barmode="stack",
        facet_col="currency" if len(_currency_values(plot_data)) > 1 else None,
        facet_col_wrap=2,
        color_discrete_map=color_map,
        hover_data={"transactions": True},
    )
    figure.update_traces(
        marker_line_color="rgba(255, 255, 255, 0.42)",
        marker_line_width=0.9,
        hovertemplate=(
            "%{x}<br>%{fullData.name}: %{y:,.2f}"
            "<br>Transactions=%{customdata[0]}<extra></extra>"
        ),
    )
    figure.update_layout(
        xaxis_title="Month",
        yaxis_title="Expenses",
        legend_title_text="Category",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )
    return _apply_dashboard_theme(figure)


def monthly_category_spend_chart(monthly_category_summary: pd.DataFrame) -> go.Figure:
    """Return a month-by-month stacked expense chart for top categories."""
    if monthly_category_summary.empty:
        return _empty_figure("No month-by-month expense categories are available.")

    plot_data = monthly_category_summary.sort_values(["currency", "month"])
    color_map = _category_color_map(plot_data["category"])
    figure = px.bar(
        plot_data,
        x="month_label",
        y="expenses",
        color="category",
        barmode="stack",
        facet_col="currency" if len(_currency_values(plot_data)) > 1 else None,
        facet_col_wrap=2,
        color_discrete_map=color_map,
    )
    figure.update_traces(
        marker_line_color="rgba(255, 255, 255, 0.35)",
        marker_line_width=0.8,
        hovertemplate="%{x}<br>%{fullData.name}: %{y:.2f}<extra></extra>",
    )
    figure.update_layout(
        xaxis_title="Month",
        yaxis_title="Expenses",
        legend_title_text="Category",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )
    return _apply_dashboard_theme(figure)


def account_breakdown_chart(account_summary: pd.DataFrame) -> go.Figure:
    """Return a net-by-account comparison chart."""
    if account_summary.empty:
        return _empty_figure("No account data available.")

    plot_data = account_summary.copy()
    plot_data["label"] = (
        plot_data["bank"]
        + " / "
        + plot_data["account"]
        + " / "
        + plot_data["subaccount"]
    )

    figure = px.bar(
        plot_data,
        x="net",
        y="label",
        orientation="h",
        color="bank",
        facet_col="currency" if len(_currency_values(plot_data)) > 1 else None,
        facet_col_wrap=2,
        hover_data={"income": ":.2f", "expenses": ":.2f", "transactions": True},
        color_discrete_map=BANK_COLOR_MAP,
    )
    figure.update_traces(
        marker_line_color="rgba(255, 255, 255, 0.5)", marker_line_width=1
    )
    figure.update_layout(
        xaxis_title="Net Amount",
        yaxis_title="",
        legend_title_text="Bank",
    )
    return _apply_dashboard_theme(figure)


def forecast_chart(forecast_summary: pd.DataFrame) -> go.Figure:
    """Return actual vs expected expense chart."""
    if forecast_summary.empty:
        return _empty_figure("Not enough history is available to build a forecast.")

    melted = forecast_summary.melt(
        id_vars="category",
        value_vars=["expected", "actual"],
        var_name="series",
        value_name="amount",
    )
    figure = px.bar(
        melted,
        x="category",
        y="amount",
        color="series",
        barmode="group",
        facet_col="currency" if len(_currency_values(melted)) > 1 else None,
        facet_col_wrap=2,
        color_discrete_map={
            "expected": TRANSFER_COLOR,
            "actual": INCOME_COLOR,
        },
    )
    figure.update_traces(
        marker_line_color="rgba(255, 255, 255, 0.45)", marker_line_width=1
    )
    figure.update_layout(
        xaxis_title="Category",
        yaxis_title="Monthly Expenses",
        legend_title_text="",
    )
    return _apply_dashboard_theme(figure)


def statement_balance_chart(statement_balances: pd.DataFrame) -> go.Figure:
    """Return a closing-balance trend chart from statement summaries."""
    if statement_balances.empty:
        return _empty_figure("No statement balances are available yet.")

    figure = px.line(
        statement_balances.sort_values("statement_end_date"),
        x="statement_end_date",
        y="closing_balance",
        color="bank",
        markers=True,
        facet_row="currency" if len(_currency_values(statement_balances)) > 1 else None,
        hover_data={
            "source_file": True,
            "opening_balance": ":.2f",
            "closing_balance": ":.2f",
        },
        color_discrete_map=BANK_COLOR_MAP,
    )
    figure.update_traces(line={"width": 3}, marker={"size": 7})
    figure.update_layout(
        xaxis_title="Statement End Date",
        yaxis_title="Closing Balance",
        legend_title_text="Bank",
    )
    return _apply_dashboard_theme(figure)
