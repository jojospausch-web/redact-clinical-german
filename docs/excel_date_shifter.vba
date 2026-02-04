Sub DatumsShift()
    '========================================
    ' VBA-Makro: Date-Shifting für Arztbriefe
    '========================================
    ' Dieses Makro shiftet Daten in markierten Excel-Zellen
    ' um einen konfigurierten Offset (SHIFT_DAYS).
    '
    ' Unterstützte Formate:
    ' - DD.MM.YYYY (z.B. 21.08.2023)
    ' - DD.MM (z.B. 05.08)
    ' - D. MonatName YYYY (z.B. 5. November 2023)
    ' - D. Mon. YYYY (z.B. 5. Nov. 2023)
    ' - Datumsbereiche (z.B. vom 05.08 bis zum 21.08.2023)
    '
    ' Verwendung:
    ' 1. Zellen markieren, die Daten enthalten
    ' 2. Alt + F8 → "DatumsShift" auswählen → Ausführen
    '========================================
    
    ' ============= KONFIGURATION =============
    Const SHIFT_DAYS As Integer = 15  ' Offset in Tagen (positiv = Zukunft, negativ = Vergangenheit)
    ' =========================================
    
    Dim cell As Range
    Dim originalText As String
    Dim shiftedText As String
    Dim pattern As String
    Dim regex As Object
    Dim matches As Object
    Dim match As Object
    Dim i As Integer
    Dim dateStr As String
    Dim shiftedDate As String
    Dim replaceCount As Integer
    
    ' RegEx-Objekt erstellen
    Set regex = CreateObject("VBScript.RegExp")
    regex.Global = True
    regex.IgnoreCase = True
    
    replaceCount = 0
    
    ' Durch alle markierten Zellen iterieren
    For Each cell In Selection
        If Not IsEmpty(cell.Value) Then
            originalText = cell.Value
            shiftedText = originalText
            
            ' ========================================
            ' Format 1: Vollständiges Datum (DD.MM.YYYY)
            ' ========================================
            regex.pattern = "\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"
            Set matches = regex.Execute(originalText)
            
            If matches.Count > 0 Then
                ' Alle Matches von hinten nach vorne ersetzen (um Positionen nicht zu verschieben)
                For i = matches.Count - 1 To 0 Step -1
                    Set match = matches(i)
                    dateStr = match.Value
                    shiftedDate = ShiftDateFull(dateStr, SHIFT_DAYS)
                    
                    ' Ersetze im String
                    shiftedText = Left(shiftedText, match.FirstIndex) & _
                                  shiftedDate & _
                                  Mid(shiftedText, match.FirstIndex + match.Length + 1)
                Next i
                replaceCount = replaceCount + matches.Count
            End If
            
            ' ========================================
            ' Format 2: Kurzdatum (DD.MM ohne Jahr)
            ' ========================================
            regex.pattern = "\b(\d{1,2})\.(\d{1,2})(?!\.\d{4})\b"
            Set matches = regex.Execute(shiftedText)
            
            If matches.Count > 0 Then
                For i = matches.Count - 1 To 0 Step -1
                    Set match = matches(i)
                    dateStr = match.Value
                    shiftedDate = ShiftDateShort(dateStr, SHIFT_DAYS)
                    
                    shiftedText = Left(shiftedText, match.FirstIndex) & _
                                  shiftedDate & _
                                  Mid(shiftedText, match.FirstIndex + match.Length + 1)
                Next i
                replaceCount = replaceCount + matches.Count
            End If
            
            ' ========================================
            ' Format 3: Deutscher Monat (5. November 2023)
            ' ========================================
            regex.pattern = "\b(\d{1,2})\.\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b"
            Set matches = regex.Execute(shiftedText)
            
            If matches.Count > 0 Then
                For i = matches.Count - 1 To 0 Step -1
                    Set match = matches(i)
                    dateStr = match.Value
                    shiftedDate = ShiftDateGermanFull(dateStr, SHIFT_DAYS)
                    
                    shiftedText = Left(shiftedText, match.FirstIndex) & _
                                  shiftedDate & _
                                  Mid(shiftedText, match.FirstIndex + match.Length + 1)
                Next i
                replaceCount = replaceCount + matches.Count
            End If
            
            ' ========================================
            ' Format 4: Abgekürzter Monat (5. Nov. 2023)
            ' ========================================
            regex.pattern = "\b(\d{1,2})\.\s+(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\.?\s+(\d{4})\b"
            Set matches = regex.Execute(shiftedText)
            
            If matches.Count > 0 Then
                For i = matches.Count - 1 To 0 Step -1
                    Set match = matches(i)
                    dateStr = match.Value
                    shiftedDate = ShiftDateGermanAbbr(dateStr, SHIFT_DAYS)
                    
                    shiftedText = Left(shiftedText, match.FirstIndex) & _
                                  shiftedDate & _
                                  Mid(shiftedText, match.FirstIndex + match.Length + 1)
                Next i
                replaceCount = replaceCount + matches.Count
            End If
            
            ' Aktualisiere Zelle mit geshifteten Daten
            If shiftedText <> originalText Then
                cell.Value = shiftedText
            End If
        End If
    Next cell
    
    ' Erfolgsmeldung
    MsgBox replaceCount & " Datum/Daten wurden um " & SHIFT_DAYS & " Tage verschoben.", vbInformation, "Date-Shifting abgeschlossen"
End Sub

' ============= HILFSFUNKTIONEN =============

Function ShiftDateFull(dateStr As String, days As Integer) As String
    ' Shiftet DD.MM.YYYY Format
    Dim parts() As String
    Dim d As Integer, m As Integer, y As Integer
    Dim dateVal As Date
    
    parts = Split(dateStr, ".")
    d = CInt(parts(0))
    m = CInt(parts(1))
    y = CInt(parts(2))
    
    dateVal = DateSerial(y, m, d)
    dateVal = DateAdd("d", days, dateVal)
    
    ShiftDateFull = Format(Day(dateVal), "00") & "." & Format(Month(dateVal), "00") & "." & Year(dateVal)
End Function

Function ShiftDateShort(dateStr As String, days As Integer) As String
    ' Shiftet DD.MM Format (ohne Jahr, nutzt aktuelles Jahr als Kontext)
    Dim parts() As String
    Dim d As Integer, m As Integer, y As Integer
    Dim dateVal As Date
    
    parts = Split(dateStr, ".")
    d = CInt(parts(0))
    m = CInt(parts(1))
    y = Year(Now)  ' Nutze aktuelles Jahr
    
    dateVal = DateSerial(y, m, d)
    dateVal = DateAdd("d", days, dateVal)
    
    ' Gebe nur DD.MM zurück (ohne Jahr)
    ShiftDateShort = Format(Day(dateVal), "00") & "." & Format(Month(dateVal), "00")
End Function

Function ShiftDateGermanFull(dateStr As String, days As Integer) As String
    ' Shiftet Format: 5. November 2023
    Dim regex As Object
    Dim matches As Object
    Dim d As Integer, m As Integer, y As Integer
    Dim monthName As String
    Dim dateVal As Date
    
    Set regex = CreateObject("VBScript.RegExp")
    regex.pattern = "(\d{1,2})\.\s+(\w+)\s+(\d{4})"
    Set matches = regex.Execute(dateStr)
    
    If matches.Count > 0 Then
        d = CInt(matches(0).SubMatches(0))
        monthName = matches(0).SubMatches(1)
        y = CInt(matches(0).SubMatches(2))
        
        m = GetMonthNumber(monthName)
        dateVal = DateSerial(y, m, d)
        dateVal = DateAdd("d", days, dateVal)
        
        ' Format zurück mit deutschem Monatsnamen
        ShiftDateGermanFull = Day(dateVal) & ". " & GetMonthName(Month(dateVal)) & " " & Year(dateVal)
    Else
        ShiftDateGermanFull = dateStr ' Fallback
    End If
End Function

Function ShiftDateGermanAbbr(dateStr As String, days As Integer) As String
    ' Shiftet Format: 5. Nov. 2023
    Dim regex As Object
    Dim matches As Object
    Dim d As Integer, m As Integer, y As Integer
    Dim monthAbbr As String
    Dim dateVal As Date
    
    Set regex = CreateObject("VBScript.RegExp")
    regex.pattern = "(\d{1,2})\.\s+(\w+)\.?\s+(\d{4})"
    Set matches = regex.Execute(dateStr)
    
    If matches.Count > 0 Then
        d = CInt(matches(0).SubMatches(0))
        monthAbbr = Replace(matches(0).SubMatches(1), ".", "")
        y = CInt(matches(0).SubMatches(2))
        
        m = GetMonthNumberAbbr(monthAbbr)
        dateVal = DateSerial(y, m, d)
        dateVal = DateAdd("d", days, dateVal)
        
        ' Format zurück mit abgekürztem Monatsnamen
        ShiftDateGermanAbbr = Day(dateVal) & ". " & GetMonthAbbr(Month(dateVal)) & ". " & Year(dateVal)
    Else
        ShiftDateGermanAbbr = dateStr ' Fallback
    End If
End Function

Function GetMonthNumber(monthName As String) As Integer
    ' Konvertiert deutschen Monatsnamen zu Nummer
    Select Case LCase(monthName)
        Case "januar": GetMonthNumber = 1
        Case "februar": GetMonthNumber = 2
        Case "märz": GetMonthNumber = 3
        Case "april": GetMonthNumber = 4
        Case "mai": GetMonthNumber = 5
        Case "juni": GetMonthNumber = 6
        Case "juli": GetMonthNumber = 7
        Case "august": GetMonthNumber = 8
        Case "september": GetMonthNumber = 9
        Case "oktober": GetMonthNumber = 10
        Case "november": GetMonthNumber = 11
        Case "dezember": GetMonthNumber = 12
        Case Else: GetMonthNumber = 1 ' Fallback
    End Select
End Function

Function GetMonthNumberAbbr(monthAbbr As String) As Integer
    ' Konvertiert abgekürzten Monatsnamen zu Nummer
    Select Case LCase(monthAbbr)
        Case "jan": GetMonthNumberAbbr = 1
        Case "feb": GetMonthNumberAbbr = 2
        Case "mär": GetMonthNumberAbbr = 3
        Case "apr": GetMonthNumberAbbr = 4
        Case "mai": GetMonthNumberAbbr = 5
        Case "jun": GetMonthNumberAbbr = 6
        Case "jul": GetMonthNumberAbbr = 7
        Case "aug": GetMonthNumberAbbr = 8
        Case "sep": GetMonthNumberAbbr = 9
        Case "okt": GetMonthNumberAbbr = 10
        Case "nov": GetMonthNumberAbbr = 11
        Case "dez": GetMonthNumberAbbr = 12
        Case Else: GetMonthNumberAbbr = 1 ' Fallback
    End Select
End Function

Function GetMonthName(monthNum As Integer) As String
    ' Konvertiert Monatsnummer zu deutschem Monatsnamen
    Select Case monthNum
        Case 1: GetMonthName = "Januar"
        Case 2: GetMonthName = "Februar"
        Case 3: GetMonthName = "März"
        Case 4: GetMonthName = "April"
        Case 5: GetMonthName = "Mai"
        Case 6: GetMonthName = "Juni"
        Case 7: GetMonthName = "Juli"
        Case 8: GetMonthName = "August"
        Case 9: GetMonthName = "September"
        Case 10: GetMonthName = "Oktober"
        Case 11: GetMonthName = "November"
        Case 12: GetMonthName = "Dezember"
        Case Else: GetMonthName = "Januar" ' Fallback
    End Select
End Function

Function GetMonthAbbr(monthNum As Integer) As String
    ' Konvertiert Monatsnummer zu abgekürztem Monatsnamen
    Select Case monthNum
        Case 1: GetMonthAbbr = "Jan"
        Case 2: GetMonthAbbr = "Feb"
        Case 3: GetMonthAbbr = "Mär"
        Case 4: GetMonthAbbr = "Apr"
        Case 5: GetMonthAbbr = "Mai"
        Case 6: GetMonthAbbr = "Jun"
        Case 7: GetMonthAbbr = "Jul"
        Case 8: GetMonthAbbr = "Aug"
        Case 9: GetMonthAbbr = "Sep"
        Case 10: GetMonthAbbr = "Okt"
        Case 11: GetMonthAbbr = "Nov"
        Case 12: GetMonthAbbr = "Dez"
        Case Else: GetMonthAbbr = "Jan" ' Fallback
    End Select
End Function
