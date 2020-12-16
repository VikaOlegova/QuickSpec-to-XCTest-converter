# QuickSpec-to-XCTest-converter

# Installation

1) Copy repo
1) Install **swiftformat**
```bash
$ brew install swiftformat
```

# Usage

Script will convert every QuickSpec test file in the directory you specify.
```bash
$ cd QuickSpec-to-XCTest-converter
$ python3 main.py /path/to/tests
```

# Notes

* Search for `*.swift` files is done recursively inside all folders in the `work_dir`
* Script will skip any file which doesn't containt string `QuickSpec`
* Folder `{work_dir}/backup` will contain original files which were converted
* Check file [CustomThrowingAssertFunctions.swift](/CustomThrowingAssertFunctions.swift) for definitions of `customAssertThrowsError` and `customAssertNoThrow`
