#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
iBackupy is a Python tool to parse iTunes backups.

Copyright (c) 2023 xleven
"""

import logging
import os
import platform
import plistlib
import sqlite3
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)


class Backup:

    def __init__(self, path: str = "", udid: str = "") -> None:
        self.set_backup_dir(path)
        self.set_device(udid)

    @staticmethod
    def _get_default_backup_dir() -> Path:
        """
        See https://support.apple.com/en-us/HT204215#findiTunes
        """
        def _win():
            for folder in [r"%APPDATA%\Apple Computer\MobileSync\Backup",
                           r"%APPDATA%\Apple\MobileSync\Backup",
                           r"%USERPROFILE%\Apple Computer\MobileSync\Backup",
                           r"%USERPROFILE%\Apple\MobileSync\Backup"]:
                path = Path(os.path.expandvars(folder))
                if path.is_dir():
                    return path
            raise FileNotFoundError("Backup not found!")

        def _mac():
            folder = "~/Library/Application Support/MobileSync/Backup"
            path = Path(folder).expanduser()
            if path.is_dir():
                return path
            raise FileNotFoundError("Backup not found!")

        if platform.system() == "Darwin":
            backup_dir = _mac()
        elif platform.system() == "Windows":
            backup_dir = _win()
        else:
            raise NotImplementedError("OS not supported!")

        return backup_dir

    def set_backup_dir(self, path: str = "") -> Path:
        """
        A valid backup directory from either input or OS default
        """
        if path:
            backup_dir = Path(os.path.expandvars(path))
            if not backup_dir.is_dir():
                raise FileNotFoundError("Backup not found!")
        else:
            backup_dir = Backup._get_default_backup_dir()

        self.backup_dir = backup_dir
        return backup_dir

    def _get_device_info(self, udid: str) -> dict:
        logger.debug(f"Try reading device info of {udid}")
        device_info = {}
        manifest_file = self.backup_dir.joinpath(udid, "Manifest.plist")
        try:
            manifest = plistlib.loads(manifest_file.read_bytes())
            device_info = {
                "udid": udid,
                "name": manifest['Lockdown']['DeviceName'],
                "ios": manifest['Lockdown']['ProductVersion'],
                "serial": manifest['Lockdown']['SerialNumber'],
                "type": manifest['Lockdown']['ProductType'],
                "encrypted": manifest['IsEncrypted'],
                "passcodeSet": manifest['WasPasscodeSet'],
                "date": datetime.fromtimestamp(manifest_file.stat().st_mtime),
            }
        except FileNotFoundError:
            logger.warning("Manifest.plist not found")
        except Exception as err:
            logger.error(err)

        return device_info

    def get_device_list(self) -> list[dict]:
        """
        Get device list from backup directory

        Returns
        -------
        List of device dict with udid, date and other info
        """
        devices = [
            self._get_device_info(path.name)
            for path in self.backup_dir.iterdir()
            if path.is_dir() and len(path.name) in [25, 40]
        ]
        return devices
    
    def _load_plist_file(self, file):
        plist = {}
        try:
            logger.debug(f"Loading manifest from {file}")
            fpath = self.backup_path.joinpath(file)
            plist= plistlib.loads(fpath.read_bytes())
        except FileNotFoundError:
            logger.warning(f"{file} not found")
        except Exception as err:
            logger.warning(f"Failed to load {file}: ", err)
        return plist

    def set_device(self, udid: str) -> dict:
        """
        Set most recent backuped device if not specified
        """
        devices, device = self.get_device_list(), {}
        udids = [d["udid"] for d in devices]
        if not udid or udid not in udids:
            if len(devices) < 1:
                logger.error("No device found")
            elif len(devices) == 1:
                logger.info("Set device with only one found")
                device = devices[0]
            else:
                logger.info("Set the latest device")
                devices_sorted = sorted(
                    devices, key=lambda d: d["date"])
                device = devices_sorted[-1]
        else:
            device = devices[udids.index(udid)]
        
        udid = device.get("udid", "")
        self.backup_path = self.backup_dir.joinpath(udid)

        logger.debug(f"Device backup path {self.backup_path}")

        self.manifest = self._load_plist_file("Manifest.plist")
        self.info = self._load_plist_file("Info.plist")
        self.status = self._load_plist_file("Status.plist")

        self.apps = self._get_apps()

        self.manifest_db = self.backup_path.joinpath("Manifest.db")

        return device

    def _get_apps(self) -> dict:
        try:
            app_list = self.info.get("Installed Applications", [])
            app_info = self.manifest.get("Applications", {})
            apps = {app: app_info.get(app, {}) for app in app_list}
        except Exception as err:
            logger.warning("Failed to get app list", err)
            apps = {}
        return apps

    @staticmethod
    def _get_app_domain(app: str) -> str:
        return f"AppDomain-{app}" if app else ""

    def _parse_file_path(self, id: str) -> Path:
        """Use `fileID` field to assemble real path of file"""
        file_path = self.backup_path.joinpath(id[:2], id)
        assert file_path.is_file(), "File not found!"
        return file_path

    @staticmethod
    def _parse_file_info(file_blob: bytes) -> dict:
        """Read `file` field in Manifest.db"""
        info = plistlib.loads(file_blob)
        return info

    def get_files(self,
                  app: str = "",
                  domain: str = "",
                  relative_path: str = "",
                  file_flag: int = 1,
                  real_path: bool = True,
                  file_info: bool = False,
                  ) -> list:
        """Locate files in Manifest.db by app, domain or relativePath

        Parameters
        ----------
        app: str
            bundle identifier of app, e.g. `com.apple.Pages`
        domain: str
            app domain or group domain, e.g. `AppDomain-com.apple.Pages`
        relative_path: str
            relative path of file, e.g. `Documents/xxxxx/Res/xx.dat`
        file_flag: int, default 1
            1 for files, 2 for directories, 4 for links
        real_path: bool, default True
            whether to parse real path by fileID
        file_info: bool, default False
            whether to parse file info from manifest blob

        Returns
        -------
        files:
            A list of files, each of which is a dict with `fileID`, `domain`,
            `relativePath` and optional parsed `path` or `info` field
        """
        query = f"""
            SELECT fileID
                ,domain
                ,relativePath
                ,file
            FROM Files
            WHERE flags = {file_flag}
        """
        app_domain = self._get_app_domain(app)
        if app_domain:
            query += f" AND domain = '{app_domain}'"
        if domain:
            query += f" AND domain LIKE '%{domain}%'"
        if relative_path:
            query += f" AND relativePath LIKE '%{relative_path}%'"

        with sqlite3.connect(self.manifest_db) as conn:
            conn.row_factory = sqlite3.Row
            logger.debug(query.replace("\n", " "))
            files = conn.cursor().execute(query).fetchall()

        if files:
            files = [dict(file) for file in files]
            if real_path:
                if file_flag == 1:
                    for file in files:
                        file["path"] = self._parse_file_path(file["fileID"])
                else:
                    logger.warning(
                        "`real_path` only support `file_flag` as 1")
            if file_info:
                for file in files:
                    file["info"] = self._parse_file_info(file["file"])
            for file in files:
                del file["file"]

        return files
