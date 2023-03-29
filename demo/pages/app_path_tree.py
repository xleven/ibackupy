import streamlit as st
import pandas as pd
from pyecharts import charts
from streamlit_echarts import st_pyecharts


ss = st.session_state


def get_path_children(df_path: pd.DataFrame, level=0):
    agg = df_path.groupby(level, group_keys=True, dropna=True)
    if level+1 in df_path:
        data = [
            {
                "name": k,
                "children": get_path_children(g, level+1)
            }
            for k, g in agg if (k != "")
        ]
    else:
        data = [{"name": k} for k,_ in agg]
    return data


@st.cache_data
def get_tree_data(manifest: pd.DataFrame):
    tree_data = []
    for app in ss.app_list:
        df_app = manifest[manifest["domain"].str.contains(app)]
        if len(df_app) < 1:
            continue
        df_path = df_app["relativePath"].str.split("/", expand=True)
        data = {
            "name": app,
            "children": get_path_children(df_path)
        }
        tree_data.append(data)
    return tree_data


def echarts_app_tree(manifest: pd.DataFrame):
    tree_data = get_tree_data(manifest)
    chart = charts.Tree().add(
        "", [{"name": "root", "children": tree_data}],
        is_roam=True, collapse_interval=2
    )
    
    return chart


if "manifest" not in ss:
    st.warning("Please setup your backup first")
else:
    st_pyecharts(echarts_app_tree(ss.manifest), height="1000px")