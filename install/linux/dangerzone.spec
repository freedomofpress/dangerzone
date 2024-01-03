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

Version:        0.5.1
Release:        1%{?dist}
Summary:        Take potentially dangerous PDFs, office documents, or images and convert them to safe PDFs

License:        AGPL-3.0
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
# Package Replacements

%if 0%{?_qubes}
# Users who install Dangerzone with native Qubes support must uninstall
# Dangerzone with container support.
Conflicts:      dangerzone
%else
# Users who install Dangerzone with container support must uninstall Dangerzone
# with native Qubes support.
Conflicts:      dangerzone-qubes
%endif

################################################################################
# Package Requirements

# Base requirement for every Python package.
BuildRequires:  python3-devel

%if 0%{?_qubes}
# Qubes-only requirements (server-side)
Requires:       python3-magic
Requires:       python3-PyMuPDF
Requires:       libreoffice
# Qubes-only requirements (client-side)
Requires:       GraphicsMagick
Requires:       ghostscript
Requires:       poppler-utils
Requires:       tesseract
# Explicitly require every tesseract model:
# See: https://github.com/freedomofpress/dangerzone/issues/431
Requires:       tesseract-langpack-afr
Requires:       tesseract-langpack-amh
Requires:       tesseract-langpack-ara
Requires:       tesseract-langpack-asm
Requires:       tesseract-langpack-aze
Requires:       tesseract-langpack-aze_cyrl
Requires:       tesseract-langpack-bel
Requires:       tesseract-langpack-ben
Requires:       tesseract-langpack-bod
Requires:       tesseract-langpack-bos
Requires:       tesseract-langpack-bre
Requires:       tesseract-langpack-bul
Requires:       tesseract-langpack-cat
Requires:       tesseract-langpack-ceb
Requires:       tesseract-langpack-ces
Requires:       tesseract-langpack-chi_sim
Requires:       tesseract-langpack-chi_sim_vert
Requires:       tesseract-langpack-chi_tra
Requires:       tesseract-langpack-chi_tra_vert
Requires:       tesseract-langpack-chr
Requires:       tesseract-langpack-cos
Requires:       tesseract-langpack-cym
Requires:       tesseract-langpack-dan
Requires:       tesseract-langpack-deu
Requires:       tesseract-langpack-div
Requires:       tesseract-langpack-dzo
Requires:       tesseract-langpack-ell
Requires:       tesseract-langpack-eng
Requires:       tesseract-langpack-enm
Requires:       tesseract-langpack-epo
Requires:       tesseract-langpack-est
Requires:       tesseract-langpack-eus
Requires:       tesseract-langpack-fao
Requires:       tesseract-langpack-fas
Requires:       tesseract-langpack-fil
Requires:       tesseract-langpack-fin
Requires:       tesseract-langpack-fra
Requires:       tesseract-langpack-frk
Requires:       tesseract-langpack-frm
Requires:       tesseract-langpack-fry
Requires:       tesseract-langpack-gla
Requires:       tesseract-langpack-gle
Requires:       tesseract-langpack-glg
Requires:       tesseract-langpack-grc
Requires:       tesseract-langpack-guj
Requires:       tesseract-langpack-hat
Requires:       tesseract-langpack-heb
Requires:       tesseract-langpack-hin
Requires:       tesseract-langpack-hrv
Requires:       tesseract-langpack-hun
Requires:       tesseract-langpack-hye
Requires:       tesseract-langpack-iku
Requires:       tesseract-langpack-ind
Requires:       tesseract-langpack-isl
Requires:       tesseract-langpack-ita
Requires:       tesseract-langpack-ita_old
Requires:       tesseract-langpack-jav
Requires:       tesseract-langpack-jpn
Requires:       tesseract-langpack-jpn_vert
Requires:       tesseract-langpack-kan
Requires:       tesseract-langpack-kat
Requires:       tesseract-langpack-kat_old
Requires:       tesseract-langpack-kaz
Requires:       tesseract-langpack-khm
Requires:       tesseract-langpack-kir
Requires:       tesseract-langpack-kmr
Requires:       tesseract-langpack-kor
Requires:       tesseract-langpack-kor_vert
Requires:       tesseract-langpack-lao
Requires:       tesseract-langpack-lat
Requires:       tesseract-langpack-lav
Requires:       tesseract-langpack-lit
Requires:       tesseract-langpack-ltz
Requires:       tesseract-langpack-mal
Requires:       tesseract-langpack-mar
Requires:       tesseract-langpack-mkd
Requires:       tesseract-langpack-mlt
Requires:       tesseract-langpack-mon
Requires:       tesseract-langpack-mri
Requires:       tesseract-langpack-msa
Requires:       tesseract-langpack-mya
Requires:       tesseract-langpack-nep
Requires:       tesseract-langpack-nld
Requires:       tesseract-langpack-nor
Requires:       tesseract-langpack-oci
Requires:       tesseract-langpack-ori
Requires:       tesseract-langpack-pan
Requires:       tesseract-langpack-pol
Requires:       tesseract-langpack-por
Requires:       tesseract-langpack-pus
Requires:       tesseract-langpack-que
Requires:       tesseract-langpack-ron
Requires:       tesseract-langpack-rus
Requires:       tesseract-langpack-san
Requires:       tesseract-langpack-sin
Requires:       tesseract-langpack-slk
Requires:       tesseract-langpack-slv
Requires:       tesseract-langpack-snd
Requires:       tesseract-langpack-spa
Requires:       tesseract-langpack-spa_old
Requires:       tesseract-langpack-sqi
Requires:       tesseract-langpack-srp
Requires:       tesseract-langpack-srp_latn
Requires:       tesseract-langpack-sun
Requires:       tesseract-langpack-swa
Requires:       tesseract-langpack-swe
Requires:       tesseract-langpack-syr
Requires:       tesseract-langpack-tam
Requires:       tesseract-langpack-tat
Requires:       tesseract-langpack-tel
Requires:       tesseract-langpack-tgk
Requires:       tesseract-langpack-tha
Requires:       tesseract-langpack-tir
Requires:       tesseract-langpack-ton
Requires:       tesseract-langpack-tur
Requires:       tesseract-langpack-uig
Requires:       tesseract-langpack-ukr
Requires:       tesseract-langpack-urd
Requires:       tesseract-langpack-uzb
Requires:       tesseract-langpack-uzb_cyrl
Requires:       tesseract-langpack-vie
Requires:       tesseract-langpack-yid
Requires:       tesseract-langpack-yor
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
install -m 755 qubes/* %{buildroot}/etc/qubes-rpc
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
