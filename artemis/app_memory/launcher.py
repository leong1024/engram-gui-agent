from artemis.runtime.app_versions import adb_shell_runner

HOME_QUERY = (
    "cmd package resolve-activity --brief "
    "-a android.intent.action.MAIN -c android.intent.category.HOME"
)


def launcher_package(device_serial: str) -> str | None:
    output = adb_shell_runner(device_serial)(HOME_QUERY) or ""
    components = [line.strip() for line in output.splitlines() if "/" in line]
    return components[-1].split("/", 1)[0] if components else None
