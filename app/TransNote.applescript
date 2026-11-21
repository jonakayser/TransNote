-- TransNote.app: pick sheet music images → save MusicXML → open in MuseScore.
-- Built by scripts/make-mac-app.sh (which fills in the path to `transnote`).
-- Double-click to choose images, or drop images onto the app icon.

property transnoteCmd : "__TRANSNOTE__"
property shellSetup : "export PATH=\"$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH\" PYTHONIOENCODING=utf-8 LANG=en_US.UTF-8; "

on run
	try
		set picked to choose file with prompt "Choose the page(s) of one piece (⌘-click or ⇧-click for several):" of type {"public.image", "com.adobe.pdf"} with multiple selections allowed
	on error number -128 -- Cancel
		return
	end try
	processPages(picked)
end run

on open droppedItems
	processPages(droppedItems)
end open

on processPages(fileList)
	-- 1. Let transnote sort the pages (Image, Image 2, … Image 10) and suggest a file name.
	set args to ""
	repeat with f in fileList
		set args to args & " " & quoted form of POSIX path of f
	end repeat
	try
		set planLines to paragraphs of (do shell script shellSetup & quoted form of transnoteCmd & " plan" & args)
	on error errMsg
		showError("TransNote could not start.", errMsg)
		return
	end try
	set suggested to item 1 of planLines
	set pageList to rest of planLines

	-- 2. Ask where to save. Default: the folder the images are in.
	set suggestedFolder to do shell script "dirname " & quoted form of suggested
	set suggestedName to do shell script "basename " & quoted form of suggested
	try
		set outFile to choose file name with prompt "Save the MusicXML file for MuseScore:" default name suggestedName default location ((POSIX file suggestedFolder) as alias)
	on error number -128
		return
	end try
	set outPath to POSIX path of outFile
	if outPath does not end with ".musicxml" and outPath does not end with ".mxl" then set outPath to outPath & ".musicxml"

	-- 3. Recognise.
	set pageArgs to ""
	set pageNames to ""
	repeat with p in pageList
		set pageArgs to pageArgs & " " & quoted form of (p as text)
		set pageNames to pageNames & "  • " & (do shell script "basename " & quoted form of (p as text)) & return
	end repeat
	set progress total steps to -1
	set progress description to "Recognising " & (count of pageList) & " page(s)…"
	set progress additional description to "This can take a minute per page."
	try
		set scanReport to do shell script shellSetup & quoted form of transnoteCmd & " scan" & pageArgs & " -o " & quoted form of outPath
	on error errMsg
		showError("Recognition failed.", errMsg)
		return
	end try

	-- 4. Done.
	set answer to button returned of (display dialog scanReport & return & return & "Pages, in this order:" & return & pageNames with title "TransNote" buttons {"Show in Finder", "Close", "Open in MuseScore"} default button "Open in MuseScore")
	if answer is "Open in MuseScore" then
		do shell script "open -a \"$(ls -d /Applications/MuseScore*.app \"$HOME\"/Applications/MuseScore*.app 2>/dev/null | sort -r | head -1)\" " & quoted form of outPath & " || open " & quoted form of outPath
	else if answer is "Show in Finder" then
		do shell script "open -R " & quoted form of outPath
	end if
end processPages

on showError(headline, details)
	display dialog headline & return & return & details with title "TransNote" buttons {"OK"} default button "OK" with icon stop
end showError
