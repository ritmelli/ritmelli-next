; The result of the mic setup, included at the end of ritmelli.iss. The --microfone
; instala-todos of [Run] writes it to {tmp}\microfone.json, in ASCII (the --saida of
; machine/mic_setup.py). ritmelli.exe has no console, so the summary of the check after the
; audio restarted goes to the setup log. A device the check found silent, one that opens
; and gives no sound (a Behringer UMC 404HD, until its cable was pulled), goes on the last
; page with what to do. In silence, as the update task runs the setup, only the log. A mic
; setup that failed makes the setup exit with 9.

[CustomMessages]
pt.SilentDevice=O Windows parou de receber som do dispositivo "%1". Desconecte o cabo USB dele e conecte novamente.
en.SilentDevice=Windows stopped receiving sound from the device "%1". Unplug its USB cable and plug it back in.

[Code]
const
  MicFilterFailedExitCode = 9;

var
  MicResultRead: Boolean;
  SilentDevices: String;
  MicFilterOk: Boolean;

// The JSON string that starts at the quote in Json[I], without its quotes and with its
// escapes undone: \uXXXX is the letter again (the JSON comes in ASCII), and \b, \f, \n, \r
// and \t become a space. I ends past the closing quote
function JsonText(Json: String; var I: Integer): String;
var
  N: Integer;
begin
  Result := '';
  N := Length(Json);
  I := I + 1;
  while I <= N do begin
    if Json[I] = '"' then begin
      I := I + 1;
      Exit;
    end;
    if Json[I] = '\' then begin
      I := I + 1;
      if I > N then
        Exit;
      if Json[I] = 'u' then begin
        Result := Result + Chr(StrToIntDef('$' + Copy(Json, I + 1, 4), Ord('?')));
        I := I + 4;
      end else if Pos(Copy(Json, I, 1), 'bfnrt') > 0 then
        Result := Result + ' '
      else
        Result := Result + Json[I];  // \", \\ and \/
    end else
      Result := Result + Json[I];
    I := I + 1;
  end;
end;

// Where the value of Key starts in the JSON, past the colon and the spaces, or 0 without
// the key
function JsonValue(Json, Key: String): Integer;
begin
  // with the colon: inside a JSON string a quote comes escaped, so no device name matches
  Result := Pos('"' + Key + '":', Json);
  if Result = 0 then
    Exit;
  Result := Result + Length(Key) + 3;
  while (Result <= Length(Json)) and (Json[Result] = ' ') do
    Result := Result + 1;
end;

// The string of Key in the JSON of the mic setup ('' without the key)
function JsonString(Json, Key: String): String;
var
  I: Integer;
begin
  Result := '';
  I := JsonValue(Json, Key);
  if (I > 0) and (I <= Length(Json)) and (Json[I] = '"') then
    Result := JsonText(Json, I);
end;

// The strings of the list Key in the JSON of the mic setup, joined by '", "' for the
// sentence ('' without the key or with an empty list)
function JsonList(Json, Key: String): String;
var
  I, N: Integer;
  Item: String;
begin
  Result := '';
  I := JsonValue(Json, Key);
  N := Length(Json);
  if (I = 0) or (I > N) or (Json[I] <> '[') then
    Exit;
  I := I + 1;
  while (I <= N) and (Json[I] <> ']') do begin
    if Json[I] = '"' then begin
      Item := JsonText(Json, I);
      if Result <> '' then
        Result := Result + '", "';
      Result := Result + Item;
    end else
      I := I + 1;
  end;
end;

function MicFilterOkInJson(Json: String): Boolean;
var
  I: Integer;
begin
  I := JsonValue(Json, 'ok');
  Result := (I > 0) and (Copy(Json, I, 4) = 'true');
end;

// {tmp}\microfone.json, read once and put in the log: the summary of the check, the silent
// devices and whether the filter went on. The silent devices, or ''
function ReadMicResult: String;
var
  Json: AnsiString;
  Summary: String;
begin
  if not MicResultRead then begin
    MicResultRead := True;
    if LoadStringFromFile(ExpandConstant('{tmp}\microfone.json'), Json) then begin
      Summary := JsonString(String(Json), 'conferencia');
      if Summary = '' then
        Summary := 'devices: not checked (the audio did not restart, or the mic setup stopped before)';
      // the label v0.7.0 logs, which the crossing looks for
      Log('aparelhos: ' + Summary);
      SilentDevices := JsonList(String(Json), 'aparelhos');
      if SilentDevices <> '' then
        Log('silent devices: "' + SilentDevices + '"');
      MicFilterOk := MicFilterOkInJson(String(Json));
      if MicFilterOk then
        Log('mic filter: ok')
      else
        Log('mic filter: failed: ' + JsonString(String(Json), 'erro'));
    end else
      Log('aparelhos: no microfone.json');
  end;
  Result := SilentDevices;
end;

// The last page: the sentence goes before "Click Finish", and the box that opens Ritmelli
// moves down with it (or, when Windows asks for a restart, the two restart options)
<event('CurPageChanged')>
procedure SilentDeviceOnPage(CurPageID: Integer);
var
  Devices, Sentence, Text: String;
  Before, Down, P: Integer;
begin
  if CurPageID <> wpFinished then
    Exit;
  Devices := ReadMicResult;
  if Devices = '' then
    Exit;
  Before := WizardForm.FinishedLabel.Top + WizardForm.FinishedLabel.Height;
  Sentence := FmtMessage(CustomMessage('SilentDevice'), [Devices]);
  Text := WizardForm.FinishedLabel.Caption;
  P := Pos(SetupMessage(msgClickFinish), Text);
  if P > 0 then
    Insert(Sentence + #13#10#13#10, Text, P)
  else
    // the restart text: its blank line at the end, before the restart options, comes back
    // after the sentence
    Text := TrimRight(Text) + #13#10#13#10 + Sentence + #13#10;
  WizardForm.FinishedLabel.Caption := Text;
  WizardForm.AdjustLabelHeight(WizardForm.FinishedLabel);
  Down := WizardForm.FinishedLabel.Top + WizardForm.FinishedLabel.Height - Before;
  WizardForm.RunList.Top := WizardForm.RunList.Top + Down;
  WizardForm.YesRadio.Top := WizardForm.YesRadio.Top + Down;
  WizardForm.NoRadio.Top := WizardForm.NoRadio.Top + Down;
end;

// in silence the page does not show: the result is only in the log
<event('CurStepChanged')>
procedure MicResultInLog(CurStep: TSetupStep);
begin
  if CurStep = ssDone then
    ReadMicResult;
end;

function GetCustomSetupExitCode: Integer;
begin
  ReadMicResult;
  if MicFilterOk then
    Result := 0
  else begin
    Log('mic filter: the setup exits with ' + IntToStr(MicFilterFailedExitCode));
    Result := MicFilterFailedExitCode;
  end;
end;
