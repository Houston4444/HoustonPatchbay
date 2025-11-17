'''workaround functions for functions of python-JACK-Client that can
crash (mainly when a port is destroyed during iteration)'''

from typing import Iterator

import jack

def _list_ports(client: jack.Client, names) -> Iterator[jack.Port]:
    if not names:
        return

    idx = 0
    while True:
        name = names[idx]
        idx += 1
        
        if not name:
            break
        
        port_ptr = jack._lib.jack_port_by_name(client._ptr, name)
        if not port_ptr:
            continue
        
        try:
            port = client._wrap_port_ptr(port_ptr)
        except jack.JackError:
            continue
        yield port

def list_ports(client: jack.Client) -> Iterator[jack.Port]:
    '''workaround for `jack.Client.get_ports()`.
    The original method in jack library crashes if a port is
    destroyed during listing, this one not.
    '''
    names = jack._ffi.gc(jack._lib.jack_get_ports(
        client._ptr, b'', b'', 0x00),
        jack._lib.jack_free)
    
    yield from _list_ports(client, names)
        
def list_all_connections(
        client: jack.Client, port: jack.Port) -> Iterator[jack.Port]:
    '''workaround for `jack.Client.get_all_connections(port)`.
    The original method in jack library crashes if a port is
    destroyed during listing, this one not.'''
    names = jack._ffi.gc(
        jack._lib.jack_port_get_all_connections(client._ptr, port._ptr),
        jack._lib.jack_free)
    
    yield from _list_ports(client, names)

def set_port_registration_callback(
        client: jack.Client, callback=None, only_available=True):
    """Register port registration callback.

    Tell the JACK server to call *callback* whenever a port is
    registered or unregistered.

    All "notification events" are received in a separated non RT
    thread, the code in the supplied function does not need to be
    suitable for real-time execution.

    .. note:: This function cannot be called while the client is
        activated (after `activate()` has been called).

    .. note:: Due to JACK 1 behavior, it is not possible to get
        the pointer to an unregistering JACK Port if it already
        existed before `activate()` was called. This will cause
        the callback not to be called if *only_available* is
        ``True``, or called with ``None`` as first argument (see
        below).

        To avoid this, call `Client.get_ports()` just after
        `activate()`, allowing the module to store pointers to
        already existing ports and always receive a `Port`
        argument for this callback.

    Parameters
    ----------
    callback : callable
        User-supplied function that is called whenever a port is
        registered or unregistered.  It must have this signature::

            callback(port: Port, register: bool) -> None

        The first argument is a `Port`, `MidiPort`, `OwnPort` or
        `OwnMidiPort` object, the second argument is ``True`` if the
        port is being registered, ``False`` if the port is being
        unregistered.

        .. note:: Same as with most callbacks, no functions that
            interact with the JACK daemon should be used here.
    only_available : bool, optional
        If ``True``, the *callback* is not called if the port in
        question is not available anymore (after another JACK client
        has unregistered it).
        If ``False``, it is called nonetheless, but the first
        argument of the *callback* will be ``None`` if the port is
        not available anymore.

    See Also
    --------
    Ports.register

    """
    if callback is None:
        return lambda cb: client.set_port_registration_callback(
            cb, only_available)

    @client._callback('JackPortRegistrationCallback')
    def callback_wrapper(port_id, register, _):
        port_ptr = jack._lib.jack_port_by_id(client._ptr, port_id)
        if port_ptr:
            try:
                port = client._wrap_port_ptr(port_ptr)
            except AssertionError:
                return
        elif only_available:
            return
        else:
            port = None
        callback(port, bool(register))

    jack._check(jack._lib.jack_set_port_registration_callback(
        client._ptr, callback_wrapper, jack._ffi.NULL),
        'Error setting port registration callback')