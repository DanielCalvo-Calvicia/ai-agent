from infrastructure.outbound.config.environment import PROJECT_ROOT, EnvironmentSettings, FileResources


def install_environment(root: str = PROJECT_ROOT) -> None:
    """Gives the application its files and its settings (the two outbound ports of application/ports/outbound/environment_ports.py).
    The composition root, the scripts and the tests call it first, before the first import that reads a file."""
    from application.support.environment import install
    install(FileResources(root), EnvironmentSettings())
