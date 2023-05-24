import platform
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from ibackupy import Backup


ss = st.session_state


def get_file_size(info):
    try:
        size = info["$objects"][1]["Size"]
    except Exception:
        size = 0
    return size


@st.cache_data
def read_backup_manifest_db():
    manifest = pd.DataFrame(
        ss.bak.get_files(real_path=False, file_info=True),
        columns=["domain", "relativePath", "info"])
    manifest["size"] = manifest["info"].map(get_file_size)
    return manifest


@st.cache_data
def get_app_list(manifest):
    if ss.bak.info:
        app_list = ss.bak.info["Installed Applications"]
    else:
        app_list = manifest.loc[
            manifest["domain"].str.startswith("AppDoman-"), "domain"].unique()
    return app_list


st.title("iBackupy")

st.markdown("""
    This is a demo of [iBackupy](https://github.com/xleven/ibackupy)
    powered by [Streamlit](https://streamlit.io)

    It's recommended to run it locally while link above provided a online version
    you can just upload your Manifest.db out of iTunes backup for quick look.
""")

st.header("Setup")

if platform.system() in ["Darwin", "Windows"]:
    backup_dir = st.text_input(
        label="Backup Directory",
        value="",
        placeholder="Leave it blank for default")
    ss.bak = Backup(path=backup_dir)

    st.header("Device View")

    device_list = ss.bak.get_device_list()
    device = st.selectbox(
        label="Choose Device",
        options=device_list,
        index=0,
        format_func=lambda d: d["name"])
    if device:
        ss.bak.set_device(device["udid"])
else:
    ss.bak = Backup(path=".")
    manifest_db = st.file_uploader(
        label="Upload your Manifest.db",
        type="db",
        accept_multiple_files=False,
        help=r"""
        You can find it at
        - Mac: ~/Library/Application Support/MobileSync/Backup/xxxx-xxxxxxxx/Manifest.db
        - Win: "%APPDATA%\Apple\MobileSync\Backup\xxxx-xxxxxxxx\Manifest.db
        """
    )
    if manifest_db:
        with tempfile.NamedTemporaryFile("w+b") as dbfile:
            dbfile.write(manifest_db.getvalue())
            ss.bak.manifest_db = Path(dbfile.name)

if ss.bak.manifest_db.is_file():
    ss.manifest = read_backup_manifest_db()
    ss.app_list = get_app_list(ss.manifest)
    st.success("Manifest database loaded, see your backup on next page")