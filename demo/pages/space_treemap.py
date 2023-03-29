import streamlit as  st
import pandas as pd
import plotly.express as px


ss = st.session_state


@st.cache_data
def get_treemap_df(manifest: pd.DataFrame, level_path: list):
    for app in ss.app_list:
        manifest.loc[manifest["domain"].str.contains(app), "App"] = app
    df = pd.concat([
        manifest,
        manifest["relativePath"].str.split("/", expand=True)
    ], axis=1).groupby(level_path).sum(numeric_only=True).reset_index()
    return df


def plotly_space_treemap(manifest: pd.DataFrame, level=4):
    level_path = ["App"] + list(range(level))
    fig = px.treemap(
        data_frame=get_treemap_df(manifest, level_path),
        path=level_path,
        values="size"
    )
    return fig

if "manifest" not in ss:
    st.warning("Please setup your backup first")
else:
    st.plotly_chart(plotly_space_treemap(ss.manifest))