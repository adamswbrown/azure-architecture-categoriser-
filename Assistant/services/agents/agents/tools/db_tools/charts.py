"""
Charting tools for agents

It will be generated in the FE by Chart.js which informs this spec
"""
from typing import Literal
import pandas as pd
from pydantic import BaseModel


class ChartDataset(BaseModel):
    """
    A dataset to be charted
    """
    label: str
    data: list[float]


class ChartData(BaseModel):
    """
    A dataset to be charted

    labels are the x axis labels
    """
    labels: list
    data: list[ChartDataset]


SUPPORTED_CHART_TYPES = Literal['bar', 'line', 'doughnut']

class ChartSpec(BaseModel):
    """
    Base chart specification
    """
    type: SUPPORTED_CHART_TYPES
    data: ChartData

    @classmethod
    def from_df(cls, type: SUPPORTED_CHART_TYPES, df: pd.DataFrame, label_col: str, value_cols: list[str]):
        """
        Create a ChartSpec from a DataFrame

        Args:
            type: the type of chart to create
            df: the DataFrame containing the data
            label_col: the column to use for the x axis labels
            value_cols: the columns to use for the y axis values (one per dataset)
        """
        labels = df[label_col].tolist()
        datasets = [
            ChartDataset(
                label=col,
                data=df[col].astype(float).tolist()
            )
            for col in value_cols
        ]
        data = ChartData(
            labels=labels,
            data=datasets
        )
        return cls(
            type=type,
            data=data
        )