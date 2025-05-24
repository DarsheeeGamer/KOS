# Text Processing Commands

KOS provides a rich set of text processing commands inspired by Unix/Linux utilities. These commands allow you to manipulate text files and extract useful information from them.

## Word Count (wc)

The `wc` command prints newline, word, and byte counts for each file.

### Usage

```
wc [OPTION]... [FILE]...
```

### Options

- `-c, --bytes`: Print the byte counts
- `-m, --chars`: Print the character counts
- `-l, --lines`: Print the newline counts
- `-w, --words`: Print the word counts

### Examples

Count lines, words, and bytes in a file:
```
wc file.txt
```

Count only lines:
```
wc -l file.txt
```

Count lines, words, and bytes in multiple files:
```
wc file1.txt file2.txt
```

## Sort (sort)

The `sort` command sorts lines of text files.

### Usage

```
sort [OPTION]... [FILE]...
```

### Options

- `-b, --ignore-leading-blanks`: Ignore leading blanks
- `-f, --ignore-case`: Fold lower case to upper case characters
- `-n, --numeric-sort`: Compare according to string numerical value
- `-r, --reverse`: Reverse the result of comparisons
- `-u, --unique`: Output only the first of an equal run
- `-o, --output=FILE`: Write result to FILE instead of standard output

### Examples

Sort a file alphabetically:
```
sort file.txt
```

Sort a file numerically:
```
sort -n numbers.txt
```

Sort a file and ignore case:
```
sort -f names.txt
```

Sort a file in reverse order:
```
sort -r file.txt
```

Sort a file and output unique lines:
```
sort -u file.txt
```

## Grep (grep)

The `grep` command prints lines matching a pattern.

### Usage

```
grep [OPTION]... PATTERN [FILE]...
```

### Options

- `-i, --ignore-case`: Ignore case distinctions in patterns and data
- `-v, --invert-match`: Select non-matching lines
- `-c, --count`: Print only a count of matching lines per FILE
- `-n, --line-number`: Print line number with output lines
- `-H, --with-filename`: Print the file name for each match
- `-h, --no-filename`: Suppress the file name prefix on output
- `-r, --recursive`: Read all files under each directory, recursively
- `-E, --extended-regexp`: PATTERN is an extended regular expression
- `-F, --fixed-strings`: PATTERN is a set of newline-separated strings

### Examples

Search for a pattern in a file:
```
grep "pattern" file.txt
```

Search for a pattern in multiple files:
```
grep "pattern" file1.txt file2.txt
```

Search for a pattern, ignoring case:
```
grep -i "pattern" file.txt
```

Search for lines NOT containing a pattern:
```
grep -v "pattern" file.txt
```

Search for a pattern and show line numbers:
```
grep -n "pattern" file.txt
```

Search recursively for a pattern in all files:
```
grep -r "pattern" directory/
```

Count occurrences of a pattern:
```
grep -c "pattern" file.txt
```

## Find (find)

The `find` command searches for files in a directory hierarchy.

### Usage

```
find [PATH...] [EXPRESSION]
```

### Options

- `-name PATTERN`: File name matches PATTERN (wildcard * and ? supported)
- `-type TYPE`: File is of type TYPE (f: regular file, d: directory)
- `-size N[cwbkMG]`: File uses N units of space
  - c: bytes
  - w: 2-byte words
  - b: 512-byte blocks
  - k: kilobytes
  - M: megabytes
  - G: gigabytes
- `-empty`: File is empty and is either a regular file or a directory
- `-executable`: File is executable
- `-readable`: File is readable
- `-writable`: File is writable
- `-maxdepth LEVELS`: Descend at most LEVELS of directories below the start points
- `-mindepth LEVELS`: Do not apply any tests or actions at levels less than LEVELS

### Examples

Find all .txt files in the current directory and subdirectories:
```
find . -name "*.txt"
```

Find all empty directories:
```
find . -type d -empty
```

Find all files larger than 1MB:
```
find . -type f -size +1M
```

Find all .py files in a specific directory, limited to depth 2:
```
find /path/to/dir -maxdepth 2 -name "*.py"
```

## Cut (cut)

The `cut` command removes sections from each line of files.

### Usage

```
cut [OPTION]... [FILE]...
```

### Options

- `-b, --bytes=LIST`: Select only these bytes
- `-c, --characters=LIST`: Select only these characters
- `-d, --delimiter=DELIM`: Use DELIM instead of TAB for field delimiter
- `-f, --fields=LIST`: Select only these fields
- `-s, --only-delimited`: Do not print lines not containing delimiters

### Examples

Extract the first and third colon-delimited fields:
```
cut -d':' -f1,3 /etc/passwd
```

Extract the first 5 characters of each line:
```
cut -c1-5 file.txt
```

Extract the second field using semicolon as delimiter:
```
cut -d';' -f2 data.csv
```

## Paste (paste)

The `paste` command merges lines of files.

### Usage

```
paste [OPTION]... [FILE]...
```

### Options

- `-d, --delimiters=LIST`: Use characters from LIST instead of TABs
- `-s, --serial`: Paste one file at a time instead of in parallel

### Examples

Merge lines from two files with TAB separators:
```
paste file1.txt file2.txt
```

Merge lines with colon separators:
```
paste -d':' file1.txt file2.txt
```

Paste files serially (one after another):
```
paste -s file1.txt file2.txt
```

## Translate (tr)

The `tr` command translates or deletes characters.

### Usage

```
tr [OPTION]... SET1 [SET2]
```

### Options

- `-c, --complement`: Use the complement of SET1
- `-d, --delete`: Delete characters in SET1, do not translate
- `-s, --squeeze-repeats`: Replace repeated characters in output with single occurrence

### Examples

Convert lowercase to uppercase:
```
cat file.txt | tr 'a-z' 'A-Z'
```

Remove all newlines:
```
cat file.txt | tr -d '\n'
```

Replace multiple spaces with a single space:
```
cat file.txt | tr -s ' '
```

## Unique (uniq)

The `uniq` command filters adjacent matching lines from input.

### Usage

```
uniq [OPTION]... [INPUT [OUTPUT]]
```

### Options

- `-c, --count`: Prefix lines by the number of occurrences
- `-d, --repeated`: Only print duplicate lines, one for each group
- `-D`: Print all duplicate lines
- `-f, --skip-fields=N`: Avoid comparing the first N fields
- `-i, --ignore-case`: Ignore differences in case when comparing
- `-s, --skip-chars=N`: Avoid comparing the first N characters
- `-u, --unique`: Only print unique lines

### Examples

Remove duplicate adjacent lines:
```
uniq file.txt
```

Show count of occurrences for each line:
```
uniq -c file.txt
```

Show only lines that appear more than once:
```
uniq -d file.txt
```

Show only lines that appear exactly once:
```
uniq -u file.txt
```

## Compare (comm)

The `comm` command compares two sorted files line by line.

### Usage

```
comm [OPTION]... FILE1 FILE2
```

### Options

- `-1`: Suppress column 1 (lines unique to FILE1)
- `-2`: Suppress column 2 (lines unique to FILE2)
- `-3`: Suppress column 3 (lines that appear in both files)
- `--output-delimiter=STR`: Use STR as the output delimiter

### Examples

Compare two files and show unique and common lines:
```
comm file1.txt file2.txt
```

Show only lines unique to first file:
```
comm -23 file1.txt file2.txt
```

Show only lines unique to second file:
```
comm -13 file1.txt file2.txt
```

Show only lines common to both files:
```
comm -12 file1.txt file2.txt
```

## Expand (expand)

The `expand` command converts tabs to spaces.

### Usage

```
expand [OPTION]... [FILE]...
```

### Options

- `-i, --initial`: Do not convert tabs after non blanks
- `-t, --tabs=N`: Have tabs N characters apart, not 8
- `-t, --tabs=LIST`: Use comma separated list of tab positions

### Examples

Convert all tabs to spaces:
```
expand file.txt
```

Convert tabs to 4 spaces:
```
expand -t 4 file.txt
```

Convert only initial tabs:
```
expand -i file.txt
```

## Fold (fold)

The `fold` command wraps each input line to fit in specified width.

### Usage

```
fold [OPTION]... [FILE]...
```

### Options

- `-b, --bytes`: Count bytes rather than columns
- `-s, --spaces`: Break at spaces
- `-w, --width=WIDTH`: Use WIDTH columns instead of 80

### Examples

Wrap lines to 60 characters:
```
fold -w 60 file.txt
```

Wrap lines to 40 characters, breaking at spaces:
```
fold -w 40 -s file.txt
```

## Combining Commands

KOS text processing commands can be combined with output redirection to create powerful workflows. For example:

1. Count the number of lines containing "error" in a log file:
```
grep "error" log.txt | wc -l
```

2. Sort a file, remove duplicates, and save to a new file:
```
sort file.txt | uniq > output.txt
```

3. Find all Python files and count them:
```
find . -name "*.py" | wc -l
```

4. Extract the first field from a CSV file and show unique values with counts:
```
cut -d',' -f1 data.csv | sort | uniq -c
```

5. Compare two sorted files and see only their differences:
```
sort file1.txt > sorted1.txt
sort file2.txt > sorted2.txt
comm -3 sorted1.txt sorted2.txt
```

6. Wrap a file to 60 characters width after converting tabs to spaces:
```
expand file.txt | fold -w 60 -s
```

These text processing commands provide essential functionality for working with text files in the KOS environment.
