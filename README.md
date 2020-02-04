# Codegrepper

Pure python, self-contained, silly implementation of a SAST tool.

Codegrepper is a very simple python script designed to grep a codebase searching for known vulnerabilities, or custom regex by choice. Due to its very limited functionalities, it can be seen as an extension of the standard unix `grep` tool, with the addition of a set of known signatures to spot common vulnerabilities, or indicators of such vulnerabilities.

The main advantage of the tool is that it is just a single file, so very light, and python based, so it can be freely run on whatever platform.

## Usage

Codegrepper has a bunch of options that can be used to ease the scan of the codebase, below:

```
usage: codegrepper.py [-h] [-d DIRECTORY] [-f FILTER] [-r REGEX] [-c CATEGORY]
                      [-s SUBCATEGORY] [-i]

Codegrepper - A simple code auditor by d3adc0de

optional arguments:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Directory to start enumeration
  -f FILTER, --filter FILTER
                        File extension filter
  -r REGEX, --regex REGEX
                        Custom regex
  -c CATEGORY, --category CATEGORY
                        Category [# to get category list]
  -s SUBCATEGORY, --subcategory SUBCATEGORY
                        Subcategories [# to get subcategory list]
  -i, --insensitive     Case insensitive search

```

A few things to notice:

* Extension filtering is done on a whitelist approach (-f php will scan only .php files)
* Regex may be whatever Python `re` based regex
* Category is one of dotnet, java, perl, php, nodejs, python, ruby or owasp (more will be added in future)
* Subcategory may vary depending on the choosen language

## Contributing

In the unlikely event you would like to contribute, please fork the repository at [https://github.com/klezVirus/codegrepper](https://github.com/klezVirus/codegrepper) and use that. Any help is very welcome.

If you want to get in touch with me github is your best choice.

## Credits

Most of the signatures are taken as is or refined by other tools, so many thanks to:

* Matthias Endler - [https://endler.dev/awesome-static-analysis/](https://endler.dev/awesome-static-analysis/)
* Wireghoul - [http://www.justanotherhacker.com](http://www.justanotherhacker.com)
* Ajin Araham - [https://ajinabraham.com](https://ajinabraham.com)
