profile_dangerzone() {
	profile_virt
	profile_abbrev="dangerzone"
	title="Dangerzone"
	desc="Copied from virt but with extra apks and an apkovl"
	apkovl="genapkovl-dangerzone.sh"
	apks="$apks podman dropbear autossh python3 sudo"
}
