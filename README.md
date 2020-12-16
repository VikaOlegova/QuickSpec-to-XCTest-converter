# QuickSpec-to-XCTest-converter

# Installation

1) Copy repo
1) Install **swiftformat**
```bash
$ brew install swiftformat
```

# Usage

1) Change path to your tests folder in `main.py`

    `work_dir = '/Users/../projects/PROJ/PROJTests'`
1) `cd QuickSpec-to-XCTest-converter` and run `python3 main.py`
1) QuickSpec tests in the `work_dir` are now converted to XCTest
1) PROFIT

# Notes

* Folder `{work_dir}/backup` will contain original files which were converted
* Search for `*.swift` files is done recursively inside all folders in the `work_dir`
* Check file [CustomThrowingAssertFunctions.swift](/CustomThrowingAssertFunctions.swift) for definitions of `customAssertThrowsError` and `customAssertNoThrow`
