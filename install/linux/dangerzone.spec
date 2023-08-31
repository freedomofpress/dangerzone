################################################################################
# Dangerzone RPM SPEC
#
# This SPEC file describes how `rpmbuild` can package Dangerzone into an RPM
# file. It follows the most recent (as of writing this) Fedora guidelines on
# packaging a Python project:
#
#     https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/
#
# Some things of note about this SPEC file:
#
# 1. It expects a `dangerzone-<version>.tar.gz` package under SOURCES. It is
#    best not to invoke `tar` yourself, but create a Python source distribution
#    instead, via `poetry build`.
# 2. It detects the `_qubes` parameter. If 1, it will build a package
#    tailored for installation in Qubes environments. Else, it will build a
#    regular RPM package. The key differences between these packages are that:
#
#    * Qubes packages include some extra files under /etc/qubes-rpc, whereas
#      regular RPM packages include the container image under
#      /usr/share/container.tar.gz
#    * Qubes packages have some extra dependencies.
# 3. It is best to consume this SPEC file using the `install/linux/build-rpm.py`
#    script, which handles the necessary scaffolding for building the package.

################################################################################
# Package Description

%if 0%{?_qubes}
Name:           dangerzone-qubes
%else
Name:           dangerzone
%endif

Version:        0.4.2
Release:        1%{?dist}
Summary:        Take potentially dangerous PDFs, office documents, or images and convert them to safe PDFs

License:        MIT
URL:            https://dangerzone.rocks

# XXX: rpmbuild attempts to find a tarball in SOURCES using the basename in the
# Source0 url. In our case, GitHub uses `v<version>.tar.gz`. However, the name
# of the source distribution that `poetry build` creates is
# `dangerzone-<version>.tar.gz`, so rpmbuild cannot find it.
#
# Taking a hint from SecureDrop Workstation, we can fix this by adding an
# innocuous URL fragment. For more details, see:
#
#     https://docs.fedoraproject.org/en-US/packaging-guidelines/SourceURL/#_troublesome_urls
Source0:        https://github.com/freedomofpress/dangerzone/archive/refs/tags/v%{version}.tar.gz#/dangerzone-%{version}.tar.gz

################################################################################
# Package Requirements

# Base requirement for every Python package.
BuildRequires:  python3-devel

%if 0%{?_qubes}
# Qubes-only requirements
Requires:       python3-magic
Requires:       libreoffice
Requires:       tesseract
%else
# Container-only requirements
Requires:       podman
%endif

%description
Dangerzone is an open source desktop application that takes potentially
dangerous PDFs, office documents, or images and converts them to safe PDFs.
It uses disposable VMs on Qubes OS, or container technology in other OSes, to
convert the documents within a secure sandbox.

################################################################################
# Package Build Instructions

%prep
%autosetup -p1 -n dangerzone-%{version}

# XXX: Replace the PySide6 dependency in the pyproject.toml file with PySide2,
# since the former does not exist in Fedora. Once we can completely migrate to
# Qt6, we should remove this. For more details, see:
#
#    https://github.com/freedomofpress/dangerzone/issues/211
sed -i 's/^PySide6.*$/PySide2 = "*"/' pyproject.toml

# XXX: Replace all [tool.poetry.group.*] references in pyproject.toml with
# [tool.poetry.dev-dependencies], **ONLY** for Fedora 37.
#
# Fedora 37 ships python3-poetry-core v1.0.8. This version does not understand
# the dependency groups that were added in v1.2.0 [1]. Therefore, we need to
# dumb down the pyproject.toml file a bit, so that poetry-core can parse it.
# Note that the dev dependencies are not consulted for the creation of the RPM
# file, so doing so should be safe.
#
# The following sed invocations turn the various [tool.poetry.group.*] sections
# into one large [tool.poetry.dev-dependencies] section. Then, they patch the
# minimum required poetry-core version in pyproject.toml, to one that can be
# satisfied from the Fedora 37 repos.
#
# TODO: Remove this workaround once Fedora 37 (fedora-37) is EOL.
#
# [1]: https://python-poetry.org/docs/managing-dependencies/#dependency-groups
%if 0%{?fedora} == 37
sed -i 's/^\[tool.poetry.group.package.*$/[tool.poetry.dev-dependencies]/' pyproject.toml
sed -i '/^\[tool.poetry.group.*$/d' pyproject.toml
sed -i 's/poetry-core>=1.2.0/poetry-core>=1.0.0/' pyproject.toml
%endif

%generate_buildrequires
%pyproject_buildrequires -R

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files dangerzone

# Create some extra directories for non-Python data, which are not covered by
# pyproject_save_files.
install -m 755 -d %{buildroot}/usr/share/
install -m 755 -d %{buildroot}/usr/share/applications/
install -m 755 -d %{buildroot}/usr/share/dangerzone/
install -m 644 install/linux/* %{buildroot}/usr/share/applications/
install -m 644 share/* %{buildroot}/usr/share/dangerzone

# In case we create a package for Qubes, add some extra files under
# /etc/qubes-rpc.
%if 0%{?_qubes}
install -m 755 -d %{buildroot}/etc/qubes-rpc
install -m 644 qubes/* %{buildroot}/etc/qubes-rpc
%endif

# The following files are included in the top level of the Python source
# distribution, but they are moved in other places in the final RPM package.
# They are considered stale, so remove them to appease the RPM check that
# ensures there are no unhandled files.
rm %{buildroot}/%{python3_sitelib}/README.md
rm -r %{buildroot}%{python3_sitelib}/install

%files -f %{pyproject_files}
/usr/bin/dangerzone
/usr/bin/dangerzone-cli
/usr/share/
%license LICENSE
%doc README.md

%if 0%{?_qubes}
# Include some configuration files for Qubes.
/etc/qubes-rpc
%endif

# Remove any stale .egg-info directories, to help users affected by
# https://github.com/freedomofpress/dangerzone/issues/514
%post
rm -rfv %{python3_sitelib}/dangerzone-*.egg-info

%changelog
%autochangelog
