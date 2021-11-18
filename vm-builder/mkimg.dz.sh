profile_dz() {
	profile_virt
	profile_abbrev="dz"
	title="Dangerzone"
	desc="Copied from virt but with extra apks and an apkovl"
	apkovl="genapkovl-dz.sh"
	apks="$apks podman dropbear autossh python3 sudo"
}
