On Error Resume Next
Dim objWMIService, colOptionalFeatures, objFeature
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
Set colOptionalFeatures = objWMIService.ExecQuery("SELECT * FROM Win32_OptionalFeature WHERE Name = 'VirtualMachinePlatform'")
For Each objFeature in colOptionalFeatures
    If objFeature.InstallState = 1 Then
        Session.Property("VIRTUALMACHINEPLATFORM_ENABLED") = "1"
    End If
Next
