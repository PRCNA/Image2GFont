using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
class Launcher {
 [STAThread] static int Main(string[] args) {
  string root=AppDomain.CurrentDomain.BaseDirectory;
  try {
   var info=new ProcessStartInfo(Path.Combine(root,@"runtime\vision\pythonw.exe"));
   info.Arguments="-E -s \""+Path.Combine(root,"desktop_app.py")+"\"";
   if(Array.IndexOf(args,"--smoke-test")>=0) info.Arguments+=" --smoke-test";
   info.WorkingDirectory=root; info.UseShellExecute=false; info.CreateNoWindow=true;
   info.EnvironmentVariables.Remove("PYTHONHOME");info.EnvironmentVariables.Remove("PYTHONPATH");
   using(var p=Process.Start(info)){p.WaitForExit();return p.ExitCode;}
  } catch(Exception e){MessageBox.Show(e.Message,"Image2GFont");return 1;}
 }
}
