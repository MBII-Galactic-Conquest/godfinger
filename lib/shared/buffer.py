
import pickle;
import sys;
from typing import Self;

BE = sys.byteorder == 'big';

class Buffer():

    DEFAULT_SIZE = 128;

    def __init__(self, approxSize = DEFAULT_SIZE, target : bytearray = None):
        if target != None:
            self._bytes = target;
        else:
            self._bytes = bytearray(approxSize);
        self._size = len(self._bytes);
        self._readPos = 0;
        self._writePos = 0;

    def _Grow(self, size = DEFAULT_SIZE):
        nbytes = bytearray(self._size + size);
        l = len(self._bytes);
        for i in range (l):
            nbytes[i] = self._bytes[i];
        del self._bytes;
        self._bytes = nbytes;
        self._size += size;
    
    def __repr__(self):
        return "[Read/Write Buffer] bytes:" + str(self._bytes) + " size : " + str(self._size) + " read/write pos : " + str(self._readPos) + ";" + str(self._writePos);
    
    def GetSize(self):
        return self._size;

    def GetEffective(self):
        result = self.GetWritten() - self.GetRead();
        if result < 0:
            result = 0;
        return result;

    def GetRead(self):
        return self._readPos;

    def GetWritten(self):
        return self._writePos;

    # just resets read/write pointers and clears internal buffers if cleanup is True
    def Drop(self, cleanup = False):
        if cleanup:
           self.Clear();
        self._readPos = 0;
        self._writePos = 0;
    
    # Drops then creates new buffer as if was constructed
    def Reset(self):
        self.Drop();
        self._bytes = bytearray(Buffer.DEFAULT_SIZE);
        self._size = Buffer.DEFAULT_SIZE;

    def Clear(self):
        l = len(self._bytes);
        for i in range(l):
            self._bytes[i] = 0;

    def WriteGrow(self, size = DEFAULT_SIZE):
        if size + self._writePos >= self._size:
            self._Grow(128 + size);

    def Write(self, b : bytes):
        l = len(b);
        self.WriteGrow(l);
        for i in range(l):
            self._bytes[self._writePos+i] = b[i];
        self._writePos += l;
    
    def WriteBool(self, b):
        self.WriteGrow(1);
        self._bytes[self._writePos] = b;
        self._writePos += 1;
    
    def WriteInt8(self, i8):
        self.WriteGrow(1);
        self._bytes[self._writePos] = i8;
        self._writePos += 1;
    
    def WriteInt16(self, i16):
        self.WriteGrow(2);
        for i in range(2):
            self._bytes[self._writePos] = ( i16 >> ( 8 - ( i * 8 ) ) & 0xFF );
            self._writePos += 1;
        
    def WriteInt32(self, i32):
        self.WriteGrow(4);
        for i in range(4):
            self._bytes[self._writePos] = ( i32 >> ( 24 - ( i * 8 ) ) & 0xFF );
            self._writePos += 1;
    
    def WriteString(self, stringus : str, encoding = "utf-8"):
        l = len(stringus);
        self.WriteInt32(l); # store size
        self.Write(stringus.encode(encoding));
    
    def __lshift__(self, other):
        bb = pickle.dumps(other);
        self.Write(bb);
    
    def CanRead(self, length):
        if self._readPos + length >= self._size:
            return False;
        else:
            return True;

    def HasToRead(self) -> bool:
        return self.GetEffective() > 0;

    def Read(self, length) -> bytearray:
        result = None;
        if not self.CanRead(length):
            return result;

        result = self._bytes[self._readPos:self._readPos + length];
        self._readPos += length;
        return result;

    def ReadAsBytes(self, length) -> bytes:
        ba = self.Read(length);
        if ba == None:
            return None;
        else:
            return bytes(ba);

    # creates a buffer copy with working set of internal buffer slice with len of length
    def ReadAsBuf(self, length) -> Self:
        result = Self(target = self.Read(length));
        return result;

    # size of 1 byte, 0 and less is false, more is true
    def ReadBool(self) -> bool:
        result = False;
        if not self.CanRead(1):
            return result;
        else:
            result = self._bytes[self._readPos];
            self._readPos += 1;
        return result;

    # size of 1 byte
    def ReadInt8(self) -> int:
        result = 0;
        if not self.CanRead(1):
            return result;
        else:
            result = self._bytes[self._readPos];
            self._readPos += 1;
        return result;

    # size of 2 byte
    def ReadInt16(self) -> int:
        result = 0;
        if not self.CanRead(2):
            return result;
        else:
            for i in range(2):
                result |= int(self._bytes[self._readPos]) >> (i * 8);
                self._readPos += 1;
        return result;

    # size of 4 byte
    def ReadInt32(self) -> int:
        result = 0;
        if not self.CanRead(4):
            return result;
        else:
            for i in range(4):
                result |= int(self._bytes[self._readPos]) >> (i * 8);
                self._readPos += 1;
        return result;

    def ReadString(self, encoding = "utf-8") ->str:
        result = "";
        l = self.ReadInt32();
        if l > 0:
            result += self.Read(l).decode(encoding);
        return result;

    # def __rshift__(self, other):
    #     size = sys.getsizeof(other);
    #     bb = self.Read(size);
    #     other = pickle.loads(bb);

    def Peek(self, length) -> bytearray:
        result = None;
        readPos = self._readPos;
        result = self.Read(length);
        self._readPos = readPos;
        return result;
