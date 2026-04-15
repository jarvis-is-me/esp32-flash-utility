## ESP32 Flash Utility 
This pyside + esptool based tool is supposed to be a way to communicate with Espressif based chips and provide a UI to -
  1. Read and display flashed filesystems and their contents (LittleFS, SPIFFS, FatFS)
  2. Create filesystems and upload them to ESP32.
  3. Create and add files to exiting filesystem living on ESP32. 
  4. Other potentially useful ESP flash related functions such as reading the eFUSE registers and displaying them, reading the NVS storage , etc.

### How to use ?
  1. You will need python 3.9+ (i have written this using python 3.13, so prefer to use that if you can)
  2. download the repo, the entry point is in `main.py`. Install the requirements from `requirements.txt` by doing `py -m pip install -r requirements.txt`
  3. Simply run `py -m main` to run the app.
  **NOTE** - Since the library does a lot of printing to the terminal , it is highly recommended to use a terminal app directly and avoid the integrated "run" terminals in IDEs such as in pycharm. Also, if you notice the reads failing a lot, try to use a lower speed. 115200 will always work. 
---
### V 0.1 -
- This is the very first release that implements the functionality of reading a LittleFS filesystem from ESP32 and displays it in a file explorer type of view.
- The user only needs to specify the offset of partition table (The default is 0x8000). This tool then fetches the partition table, searches for the a filesystem partition , then reads the partition.
- After reading the partition , it creates a tree view and shows it to the user.
- The user can currently double click file name and open any text based file and view its contents
<img width="1285" height="754" alt="image" src="https://github.com/user-attachments/assets/d16c4abe-d0eb-4e32-aa9c-a7890b1c6e1b" />
<img width="1282" height="752" alt="image" src="https://github.com/user-attachments/assets/b2bb6bff-927a-4ba6-8c08-eae5f00ecce4" />
<img width="1283" height="755" alt="image" src="https://github.com/user-attachments/assets/7dd9ffe4-3cff-4d48-b46e-23eb9f8caf69" />

#### Known drawbacks -
  1. The user wont be able to preview image or binary files, only text based files such as .json , .txt , .html etc.
  ~~2. The user has no feedback in the GUI for the reading happening , the progress is logged in the terminal.~~ Progress is now shown as progress bar
  ~~3. The filesystem read happens on the main thread, so the UI is unrespnosive for the reading of filesystem (takes about 19 seconds to read a 1.5MB filesystem at 921600 baud rate on my machine)~~ Moved into a fully seperate process
  4. The UI , appearance wise looks like it might give someone migraine. Currently, my focus is mainly on getting the app functionality to work. However, styling will come soon as well.  
  5. and a lot more polishing is required.

#### Things coming in immediate next version -
  ~~1. Running the reading of flash on seperate thread and keeping the UI responsive~~ DONE
  ~~2. Having a progress bar to show much % is done.~~ DONE
  3. Ability to preview image files and potentially binary files
  4. Refining the error handling and providing better error messages to the user.
  5. Ability to load a filesystem from existing .bin file. 
