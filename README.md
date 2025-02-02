# bookgen

This is a simple python script that allows you to convert PGN files to ones that are usable for opening books. The output of the script is a binary file that contains information in the following format:

```
hash: u64,        // 8 bytes
source: u8,       // 1 byte
target: u8,       // 1 byte
promotion: u8,    // 1 byte
moveType: u8,     // 1 byte
piece: u8,        // 1 byte
weight: u16,      // 2 bytes
learn: u16,       // 2 bytes
```

Because Zig automatically pads packed structs to be in 8-byte segments, our Python script also does the same thing. 7 additional padding bits are added to the end of each book entry.

### Usage

The paths are hard coded in the main function, you can edit them to fit your needs.
```
git clone git@github.com:strvdr/bookgen.git
cd bookgen
venv venv
source ./bin/venv/activate
python3 -m pip install -r requirements.txt
python3 pgn_to_book.py
```
 
If you need an example of how to make this work with your engine, you can view the implementation in the (Syzygy.zig file of Kirin Chess)[https://github.com/strvdr/kirin-chess].
