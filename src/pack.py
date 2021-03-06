# This library is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see
# <http://www.gnu.org/licenses/>.



""" Utility module for unpacking shapes of binary data from a buffer
or stream. """

# TODO: maybe one day in the future we'll add a Packer to this. If we
# ever get to the point where we want to recompile a class from a
# JavaClassInfo instance.

# profiling showed a significant amount of time spent in this module,
# so there will be efforts here to increase performance



from struct import Struct



def compile_struct(fmt, cache=dict()):

    """ returns a struct.Struct instance compiled from fmt. If fmt has
    already been compiled, it will return the previously compiled
    Struct instance. """

    sfmt = cache.get(fmt, None)
    if not sfmt:
        sfmt = Struct(fmt)
        cache[fmt] = sfmt
    return sfmt



class _Unpacker(object):

    """ (abstract) base class for StreamUnpacker and BufferUnpacker,
    hold common code"""


    def __enter__(self):
        return self


    def __exit__(self, exc_type, _exc_val, _exc_tb):
        self.close()
        return (exc_type is None)


    def unpack(self, format_str):

        """ unpacks the given format_str from the underlying data and
        returns the results. Will raise an UnpackException if there is
        not enough data to satisfy the specified format """

        pass


    def unpack_struct(self, struct):

        """ unpacks the given struct from the underlying data and
        returns the results. Will raise an UnpackException if there is
        not enough data to satisfy the format of the structure """

        pass


    def read(self, count):

        """ read count bytes from the unpacker and return it. Raises
        an UnpackException if there is not enough data in the
        underlying stream. """

        pass


    def close(self):

        """ close this unpacker and release the underlying data """

        pass


    def unpack_array(self, fmt):

        """ reads a count from the unpacker, and unpacks fmt count
        times. Yields a sequence of the unpacked data tuples """

        (count,) = self.unpack_struct(_H)
        sfmt = compile_struct(fmt)
        for _i in xrange(count):
            yield self.unpack_struct(sfmt)



    def unpack_struct_array(self, struct):

        """ reads a count from the unpacker, and unpacks the
        precompiled struct count times. Yields a sequence of the
        unpacked data tuples """

        (count,) = self.unpack_struct(_H)
        for _i in xrange(count):
            yield self.unpack_struct(struct)
        


    def unpack_objects(self, atype, *params, **kwds):

        """ reads a count from the unpacker, and instanciates that
        many calls to atype, with the given params and kwds passed
        along. Each instance then has its unpack method called with
        this unpacker instance passed along. Yields a squence of the
        unpacked instances """

        (count,) = self.unpack_struct(_H)
        for _i in xrange(count):
            obj = atype(*params, **kwds)
            obj.unpack(self)
            yield obj



class BufferUnpacker(_Unpacker):

    """ Unpacker wrapping a str or buffer. """


    def __init__(self, data, offset=0):
        _Unpacker.__init__(self)

        self.data = data
        self.offset = offset


    def unpack(self, fmt):

        """ unpacks the given fmt from the underlying buffer and
        returns the results. Will raise an UnpackException if there is
        not enough data to satisfy the fmt """

        sfmt = compile_struct(fmt)
        size = sfmt.size

        offset = self.offset
        avail = len(self.data) - offset

        if avail < size:
            raise UnpackException(fmt, size, avail)

        self.offset = offset + size
        return sfmt.unpack_from(self.data, offset)


    def unpack_struct(self, struct):

        """ unpacks the given struct from the underlying buffer and
        returns the results. Will raise an UnpackException if there is
        not enough data to satisfy the format of the structure """

        offset = self.offset
        avail = len(self.data) - offset

        size = struct.size

        if avail < size:
            raise UnpackException(struct.format, size, avail)

        self.offset = offset + size
        return struct.unpack_from(self.data, offset)


    def read(self, count):

        """ read count bytes from the underlying buffer and return
        them as a str. Raises an UnpackException if there is not
        enough data in the underlying buffer."""

        if not self.data:
            raise UnpackException(None, count, 0)

        offset = self.offset
        avail = len(self.data) - offset

        if avail < count:
            raise UnpackException(None, count, avail)

        self.offset = offset + count
        return self.data[offset:self.offset]


    def close(self):

        """ release the underlying buffer """

        self.data = None
        self.offset = 0



class StreamUnpacker(_Unpacker):

    """ Wraps a stream (or creates a stream for a string or buffer)
    and advances along it while unpacking structures from it.

    This class adheres to the context management protocol, so may be
    used in conjunction with the 'with' keyword """


    def __init__(self, data):
        _Unpacker.__init__(self)
        self.data = data


    def unpack(self, fmt):

        """ unpacks the given fmt from the underlying stream and
        returns the results. Will raise an UnpackException if there is
        not enough data to satisfy the fmt """

        sfmt = compile_struct(fmt)
        size = sfmt.size
        buff = self.data.read(size)
        if len(buff) < size:
            raise UnpackException(fmt, size, len(buff))

        return sfmt.unpack(buff)


    def unpack_struct(self, struct):

        """ unpacks the given struct from the underlying stream and
        returns the results. Will raise an UnpackException if there is
        not enough data to satisfy the format of the structure """

        size = struct.size
        buff = self.data.read(size)
        if len(buff) < size:
            raise UnpackException(struct.format, size, len(buff))

        return struct.unpack(buff)


    def read(self, count):

        """ read count bytes from the unpacker and return it. Raises
        an UnpackException if there is not enough data in the
        underlying stream. """

        if not self.data:
            raise UnpackException(None, count, 0)

        buff = self.data.read(count)
        if len(buff) < count:
            raise UnpackException(None, count, len(buff))

        return buff


    def close(self):

        """ close this unpacker, and the underlying stream if it
        supports such """

        data = self.data
        self.data = None

        if hasattr(data, "close"):
            data.close()



def unpack(data):

    """ returns either a BufferUnpacker or StreamUnpacker instance,
    depending upon the type of data. The unpacker supports the managed
    context interface, so may be used eg: `with unpack(my_data) as
    unpacker:` """

    if isinstance(data, (str, buffer)):
        return BufferUnpacker(data)

    elif hasattr(data, "read"):
        return StreamUnpacker(data)

    else:
        raise TypeError("Unpacker requires a str, buffer, or instance"
                        " supporting the read method")



class UnpackException(Exception):

    """ raised when there is not enough data to unpack the expected
    structures """

    template = "format %r requires %i bytes, only %i present"

    def __init__(self, fmt, wanted, present):
        Exception.__init__(self.template % (fmt, wanted, present))
        self.format = fmt
        self.bytes_wanted = wanted
        self.bytes_present = present



# We use this one a lot, so let's not bother calling compile_struct
# over and over to get it.
_H = compile_struct(">H")



#
# The end.
