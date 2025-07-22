# Managing Python installations

## macOS

- [ ] Verify and install the latest supported Python version from [python.org](https://www.python.org/downloads/macos/)

  > 🚨 Do not use the one from Homebrew as it is known to
  > [cause issues](https://github.com/freedomofpress/dangerzone/issues/471))


- [ ] Ensure the `~/.zprofile` of all accounts contains the following lines, and
  remove any older ones, if they exist:

  ```
  PATH="/Library/Frameworks/Python.framework/Versions/<version>/bin:${PATH}"
  export PATH
  ```

  _(make sure to replace `<version>` with the version of the newly installed
  Python, e.g., `3.13`)_

  > 🚨 When a user installs Python from python.org, it is installed by default
  > in a non-standard location
  > (`/Library/Frameworks/Python.framework/Versions/`), and can co-exist with
  > previous installations from https://python.org. In order to make it
  > accessible to the shell, the Python installer updates the `PATH` environment
  > variable. However, it does so only for the account that installs Python, and
  > not for the rest of the accounts. So, the last part must be done manually.

- [ ] Exit any previous terminal/SSH sessions, so that the `$PATH` changes can take effect.

  _(We can't just `source ~/.zshrc`, because it doesn't account for removals or
  changes in `~/.zprofile`)_

- [ ] Ensure `which python3` returns the expected Python installation

  ```
  % which python3
  /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
  ```

- [ ] Install Poetry from an account with **admin** privileges, with `python3 -m pip install -U poetry`

- [ ] Ensure `which poetry` returns the expected Poetry installation

  ```
  % which poetry
  /Library/Frameworks/Python.framework/Versions/3.13/bin/poetry
  ```

- [ ] Ensure that Poetry picks the correct Python version with `poetry debug info`

  ```shell
  % cd dangerzone
  % poetry debug info
  Poetry
  Version: 2.1.3
  Python:  3.13.5

  Virtualenv
  Python:         3.13.5
  Implementation: CPython
  Path:           [...]
  Executable:     [...]
  Valid:          True

  Base
  Platform:   darwin
  OS:         posix
  Python:     3.13.5
  Path:       [...]
  Executable: [...]
  ```

## Windows

- [ ] Verify and install the latest supported Python version from [python.org](https://www.python.org/downloads/macos/)

- [ ] Install Poetry with `python3 -m pip install -U poetry`

- [ ] Ensure that Poetry picks the correct Python version with `poetry debug info`

  ```shell
  C:\> cd dangerzone
  C:\> poetry debug info
  Poetry
  Version: 2.1.3
  Python:  3.13.5

  Virtualenv
  Python:         3.13.5
  Implementation: CPython
  Path:           [...]
  Executable:     [...]
  Valid:          True

  Base
  Platform:   win32
  OS:         nt
  Python:     3.13.5
  Path:       [...]
  Executable: [...]
  ```
