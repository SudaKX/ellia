class RegistryError(Exception):
    pass


class RegistryFrozenError(RegistryError):
    pass


class DuplicateStableIdError(RegistryError):
    pass


class EndpointNotFoundError(RegistryError):
    pass


class CallbackNotFoundError(RegistryError):
    pass
