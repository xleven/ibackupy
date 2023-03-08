# iBackupy

A Python package to parse iTunes backup.

## Install

```Bash
$ pip install -U ibackupy
```

## Usage

```Python
from ibackupy import Backup

bak = Backup()  # or Backup(custom_backup_dir)
bak.get_device_list()
bak.set_device(device_udid)

# get files from backup
bak.get_files(
    app="com.apple.Pages",
    relative_path="xx/xx.dat",
    real_path=True,
)
```

## License

[MIT](./LICENSE)
