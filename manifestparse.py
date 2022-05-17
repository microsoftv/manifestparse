"""Usage:
  python -m manifestparse <releasemanifest> <savepath>

Arguments:
    <releasemanifest> -- path to the releasemanifest file.
    <savepath> -- path to the directory to save the release manifest to.
"""

import os
import struct
import io
import sys

def solveTempDir(strings, files, directories, tardir):
    result = {
        'name': strings[tardir['nameIndex']],
        'files': [],
        'subDirectories': []
    }
    for i in range(tardir['filesStartIndex'], tardir['filesStartIndex'] + tardir['filesCount']):
        file = files[i]
        result['files'].append({
            'name': strings[file['nameIndex']],
            'version': file['version'],
            'flags': file['flags'],
            'type': file['type'],
        })
    for i in range(tardir['subDirectoriesStartIndex'], tardir['subDirectoriesStartIndex'] + tardir['subDirectoriesCount']):
        subdir = directories[i]
        result['subDirectories'].append(solveTempDir(strings, files, directories, subdir))
    return result

def indent_string(string, indent):
    return '\n'.join(['\t' * indent + line for line in string.splitlines()])

class ManifestDirectory:
    def __init__(self, tempdir):
        self.name = tempdir['name']
        self.files = []
        self.subDirectories = []

        for i in range(len(tempdir['files'])):
            file = tempdir['files'][i]
            self.files.append(ManifestFile(file['name'], self, file['version'], file['flags'], file['type']))

        for i in range(len(tempdir['subDirectories'])):
            subdir = tempdir['subDirectories'][i]
            self.subDirectories.append(ManifestDirectory(subdir))

    def __str__(self):
        returnString = self.name + '\n'
        returnString += 'Files:\n'

        for i in range(len(self.files)):
            file = self.files[i]
            returnString += indent_string(file.__str__(), 1) + '\n'

        if (len(self.subDirectories) == 0):
            return returnString
        else:
            returnString += 'Sub Directories:\n'
            for i in range(len(self.subDirectories)):
                subdir = self.subDirectories[i]
                returnString += indent_string(subdir.__str__(), 1) + '\n'

        return returnString
        
class ManifestFile:
    def __init__(self, name, parentDirectory, version, flags, fileType):
        self.name = name
        self.parentDirectory = parentDirectory
        self.version = version
        self.flags = flags
        self.fileType = fileType

        # Known Flags:
        # 0x01 :  Managedfiles dir (?)
        # 0x02 :  Archived/Filearchives dir (?)
        # 0x04 :  (?) #
        # 0x10 :  Compressed
        # lol_air_client: all 0
        # lol_air_client_config_euw: all 0
        # lol_launcher: all & 4
        # lol_game_client: all & 4
        # lol_game_client_en_gb: all 5

    def __str__(self, indent=0):
        returnString = (' ' * indent) + self.name + '\n'
        return returnString


class ReleaseManifestFile:
    def __init__(self, file):
        with open(file, 'rb') as f:
            data = io.BytesIO(f.read())
            magic = data.read(4).decode('utf-8')
            self.type = struct.unpack('I', data.read(4))[0]
            entries = struct.unpack('I', data.read(4))[0]
            self.version = struct.unpack('I', data.read(4))[0]
            self.directories = []
            self.mainDirectories = []
            self.subDirectories = []
            self.files = []

            directoryCount = struct.unpack('I', data.read(4))[0]
            tempdirectories = []
            for i in range(directoryCount):
                tempdirectories.append({
                    'nameIndex': struct.unpack('I', data.read(4))[0],
                    'subDirectoriesStartIndex': struct.unpack('I', data.read(4))[0],
                    'subDirectoriesCount': struct.unpack('I', data.read(4))[0],
                    'filesStartIndex': struct.unpack('I', data.read(4))[0],
                    'filesCount': struct.unpack('I', data.read(4))[0]
                })

            filesCount = struct.unpack('I', data.read(4))[0]
            tempfiles = []
            for i in range(filesCount):
                # According to https://github.com/LoL-Fantome/Fantome.Libraries.League, ukn+type+ukn1+ukn2 (int64) is the date value.
                tempfiles.append({
                    'nameIndex': struct.unpack('I', data.read(4))[0],
                    'version': struct.unpack('I', data.read(4))[0],
                    'hash': data.read(16).hex().join(''),
                    'flags': struct.unpack('I', data.read(4))[0],
                    'size': struct.unpack('I', data.read(4))[0],
                    'compressedSize': struct.unpack('I', data.read(4))[0],
                    'unk': struct.unpack('I', data.read(4))[0],
                    'type': struct.unpack('H', data.read(2))[0],
                    'unk1': struct.unpack('B', data.read(1))[0],
                    'unk2': struct.unpack('B', data.read(1))[0]
                })
            
            stringsCount = struct.unpack('I', data.read(4))[0]
            # represents all file names concatenated
            stringsSize = struct.unpack('I', data.read(4))[0]

            tempstrings = []
            for i in range(stringsCount):
                # read until '\0'
                read_string = ''
                while True:
                    char = data.read(1)
                    if char == b'\0':
                        break
                    read_string += char.decode('utf-8')
                tempstrings.append(read_string)

            for i in range(directoryCount):
                newdir = ManifestDirectory(solveTempDir(tempstrings, tempfiles, tempdirectories, tempdirectories[i]))
                self.directories.append(newdir)
                for j in range(len(newdir.subDirectories)):
                    self.subDirectories.append(newdir.subDirectories[j])

                for j in range(len(newdir.files)):
                    file = newdir.files[j]
                    # check by object
                    if file in self.files:
                        continue
                    
                    self.files.append(file)

            for i in range(len(self.directories)):
                goNext = False
                dir = self.directories[i]

                for j in range(len(self.mainDirectories)):
                    if dir.name == self.mainDirectories[j].name:
                        goNext = True
                        break

                for j in range(len(self.subDirectories)):
                    if dir.name == self.subDirectories[j].name:
                        goNext = True
                        break

                if goNext:
                    continue

                self.mainDirectories.append(dir)
    def __str__(self):
        returnString = 'Release Manifest {0}\n'.format(self.version)
        returnString += 'Directories:\n'
        for i in range(len(self.mainDirectories)):
            dir = self.mainDirectories[i]
            returnString += ' ' + dir.__str__() + '\n'
        
        return returnString

def main():

    if len(sys.argv) < 1:
        print("Invalid number of arguments.")
        print(__doc__)
        sys.exit(1)

    if len(sys.argv) >= 3:
        if not os.path.exists(sys.argv[1]):
            print("File does not exist.")
            print(__doc__)
            sys.exit(1)
        
        rmf = ReleaseManifestFile(sys.argv[1])

        if len(sys.argv) == 3:
            with open('release_manifest.txt', 'w') as f:
                f.write(str(rmf))

        print("Finished parsing Release Manifest.")

    else:
        print("Invalid arguments given for realm/version.")
        print(__doc__)
        sys.exit(1)

if __name__ == '__main__':
    main()
