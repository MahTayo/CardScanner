'''
This program handles the text processing for
the automatic card scanner

Version: 4
Author: Lamine Sao
'''
from picamera2 import Picamera2, Preview
from platform import python_branch
from libcamera import controls
import cv2
import pytesseract
import numpy as np
from pytesseract import Output
import nltk 
from nltk.tokenize import word_tokenize
import time # for taking camera stills
import keyboard
import mysql.connector
from csv import writer
import os
from PIL import Image
import sys

# Set camera parameters 
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(main={"size": (3280, 2464)}, lores={"size": (640, 480)}, display="lores")
picam2.configure(camera_config)
picam2.start(show_preview=True)
# Picamera modul 3 autofocus controls: https://www.tomshardware.com/how-to/raspberry-pi-camera-module-3-python-picamera-2
picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous, "AfSpeed": controls.AfSpeedEnum.Fast})

# Set file locations
homeDirectory = input("Enter your pi home directory: ")
batchSize = 0
picSet = 0
#Declare picSet and batchSize with incorrect input rejection
def declarePicAndBatch():
    global batchSize, picSet
    #Incorrect input rejection
    initBatchSize = input("Enter the card batch size you wish to record: ")
    while initBatchSize.isdigit() != True or initBatchSize == 0:
        if initBatchSize.isdigit():
            batchSize = int(initBatchSize)
            break
        else:   
            initBatchSize = input("Please enter a valid integer for batch size: ")
    batchSize = int(initBatchSize)

    initPicSet = input("Enter picture set number: ") # Global variable for the hard drive log number
    while initPicSet.isdigit() != True:
        if initPicSet.isdigit():
            picSet = int(initPicSet)
            break
        else:
            initPicSet = input("Please enter a valid integer for picture set number: ")
    picSet = int(initPicSet)
declarePicAndBatch()


cardPicList = []
cardList = []
cardIndex = 0 # must be global otherwise resets to 0 every time, which is bad!
imagesTaken = 0
tempLocation = ""
print("Batch size: " + str(batchSize))
print("Picture set number: " + str(picSet))

#Callibration and draw_rectangle defaults
left = 0
top = 0
right = 1
bottom = 1
roi_point = []
is_button_down = False


for i in range(batchSize):
    cardPicList.append("card_" + str((i + 1)) + ".jpg")

# Initialize the camera for first image processing and take picture
def takePicture():
    global cardPicList
    global imagesTaken
    for i in range(int(batchSize)):
        take = input("Take a photo (y/n): ")
        if (take.lower() != "n"):
            imagesTaken = imagesTaken + 1
            picam2.capture_file("/home/" + homeDirectory + "/cardScanner/" + "Card_Pics_" + str(picSet) + "/" + cardPicList[i]) # Saves images to dedicated image directory for each hard drive log
            print("Image " + str(i+1) + " captured")


# Tokenization test - inspired by https://github.com/cherry247/OCR-bill-detection/blob/master/ocr.ipynb
# This function crops and image and uses pytesseract OCR to read the text inside
def textImageProcessor(imgLocation):

    uncroppedImage = Image.open(imgLocation)
    
    # Setting the points for cropped image
    
    # Cropped image of above dimension
    # (It will not change original image)
    croppedImage = uncroppedImage.crop((left, top, right, bottom))
    
    # hdImage = cv2.cvtColor(hdImage, cv2.COLOR_BGR2GRAY) # Convert to greyscale for better processing - not working right now
    
    rawText = pytesseract.image_to_data(croppedImage, output_type=Output.DICT) # Raw dictionary 
    recordedList = rawText['text'] #Text list subset of rawText diciontary
    recordedString = ' '.join(rawText['text'])
    return recordedString


def callibration(fileLocation):
    global left, top, right, bottom
    
    print("Please draw a bounding box around the serial number location")
    # load the image
    image = cv2.imread(fileLocation)

    # reference to the image
    image_clone = image

    # setup the mouse click handler
    cv2.namedWindow("Resize", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Resize", 1536, 864)
    cv2.imshow("Resize", image)
    cv2.setMouseCallback("Resize", draw_rectangle)
    try:
        exitCode = input("Press any keyboard button (except 'n') when you finish drawing the bounding box: ")
    except:
        print("Invalid input")

    
    # loop until the 'c' key is pressed
    while True:
        # display the image 
        # wait for a keypress
        if exitCode.lower() != "n":
            left = roi_point[0][0]
            top = roi_point[0][1]
            right = roi_point[1][0]
            bottom = roi_point[1][1]
            cv2.destroyAllWindows()
            break
    # close all open windows

# Source: https://towardsdatascience.com/performing-image-annotation-using-python-and-opencv-f0124746613c
def draw_rectangle(event, x, y, flags, param):
    # to indicate if the left mouse button is depressed
    global is_button_down, roi_point, tempLocation

    # load the image
    image = cv2.imread(tempLocation)

    # reference to the image
    image_clone = image
    
    if event == cv2.EVENT_MOUSEMOVE and is_button_down:

        # get the original image to paint the new rectangle
        image = image_clone.copy()

        # draw new rectangle
        cv2.rectangle(image, roi_point[0], (x,y), (0, 255, 0), 2)

    if event == cv2.EVENT_LBUTTONDOWN:
        # record the first point
        roi_point = [(x, y)]  
        is_button_down = True

    # if the left mouse button was released
    elif event == cv2.EVENT_LBUTTONUP:        
        roi_point.append((x, y))     # append the end point

        # button has now been released
        is_button_down = False

        # draw the bounding box
        cv2.rectangle(image, roi_point[0], roi_point[1], (0, 255, 0), 2)
        cv2.namedWindow("Resize", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Resize", 1536, 864)
        cv2.imshow("Resize", image)


def fixCardDataAndAdd():
    global tempLocation
    print("Recorded Card Serial Numbers: \n")
    for i in range(int(batchSize)):   
        print("Card #" + str(i+1) + ": " + cardList[i])

    needToFix = (input("Do you want to manually fix serial numbers? (Y/N): "))
    while needToFix.upper() != "Y" or needToFix.upper() != "N":
        if needToFix.upper() == "Y": # NEED TO ADD INCORRECT INPUT REJECTION ie. non integer inputs, 0 entered by accident
            try:
                cardNumToFix = int(input("Enter the number you want to fix (ie. 1, 3, 20): "))
                print("You have chosen to fix card #" + str(cardNumToFix) + ": " + cardList[cardNumToFix - 1])

                #Displays image of card that was incorrect to recallibrate
                picLoc = "/home/" + homeDirectory + "/cardScanner/Card_Pics_" + str(picSet) + "/" + cardPicList[cardNumToFix - 1]
                print("Please redraw bounding box")
                tempLocation = picLoc # to make sure draw_rectangle updates the current image

                # Recallibrate if the serial number is not read correctly
                callibration(picLoc) 
                correctedSN = textImageProcessor(picLoc)
                print("The new recorded serial number is: " + correctedSN)
                cardImage = cv2.imread(picLoc)
                cv2.namedWindow("Resize", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("Resize", 1536, 864)
                cv2.imshow("Resize", cardImage)
                enterManually = input("Has the serial number been entered correctly now? (Y/N): ")
                if enterManually.lower() == "n":
                    correctedSN = input("Enter the corrected serial number: ")
                cardList[cardNumToFix - 1] = correctedSN
                cv2.destroyAllWindows()
            except: 
                print("Invalid input")
        elif needToFix.upper() == "N":
            break
        else:
            print("Please type a valid answer")
        for i in range(int(batchSize)):   
            print("Card #" + str(i+1) + ": " + cardList[i])
        needToFix = (input("Do you want to manually fix serial numbers? (Y/N): "))

#Function that writes the HDD report
def writeReport():
    global picSet, cardList, cardIndex, tempLocation
    initialImageLocation = "/home/" + homeDirectory + "/cardScanner/Card_Pics_" + str(picSet) + "/" + cardPicList[0]

    processFromExisting = input("Would you like to input from an existing folder? (Y/N): ")

    if processFromExisting.upper() == "Y":
        print("Processing from existing folder #" + str(picSet))
    else:
        os.system("mkdir Card_Pics_" + str(picSet))
        takePicture()
    tempLocation = initialImageLocation # Make sure draw reectangle works correctly for current image
    callibration(initialImageLocation)
    for i in range(int(batchSize)):
        recordedString = textImageProcessor("/home/" + homeDirectory + "/cardScanner/Card_Pics_" + str(picSet) + "/" + cardPicList[cardIndex]) # Goes through global hard drive jpg list)
        cardList.append(recordedString)
        cardIndex = cardIndex + 1 # Prepares for next loop
    fixCardDataAndAdd()
    csvScribe()
    print("Report #" + str(picSet) + " completed")
    time.sleep(1)
    
def csvScribe():
    with open(("/home/" + homeDirectory + "/cardScanner/Card_Log.csv"), 'a', newline='') as driveLog:
        # Pass the CSV  file object to the writer() function
        writer_object = writer(driveLog)
        for x in range(int(batchSize)):
            driveData = [cardList[x]] # Column data from master list
            # Result - a writer object
            # Pass the data in the list as an argument into the writerow() function
            writer_object.writerow(driveData)  
        # Close the file object
        driveLog.close()

# This is the master function, which controls all the processes and has
# the direct override to kill the program

def looper():
    global picSet
    global cardIndex
    global imagesTaken
    writeReport()

    writeAnother = input("Would you like to complete another report? (Y/N): ")
    while writeAnother.upper() != "Y" or writeAnother.upper() != "N": # Ensures user enters valid answer - redundancy
        if writeAnother.upper() == "Y":
            declarePicAndBatch()
            cardIndex = 0
            imagesTaken = 0
            looper()
        elif writeAnother.upper() == "N":
            print("Goodbye")
            sys.exit()
        else:
            print("Please type a valid answer")
            writeAnother = input("Would you like to complete another report? (Y/N): ")




def main():
    takePicture()
    looper()
  






# Functions called here to execute the program
if __name__ == "__main__":
    main()

