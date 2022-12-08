﻿using Ghosts.Client.Infrastructure;
using Ghosts.Domain;
using Ghosts.Domain.Code;
using Newtonsoft.Json;
using OpenQA.Selenium.Support.UI;
using OpenQA.Selenium;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using NPOI.POIFS.Properties;
using Actions = OpenQA.Selenium.Interactions.Actions;
using Exception = System.Exception;
using NLog;
using static System.Windows.Forms.VisualStyles.VisualStyleElement.StartPanel;
using System.Security.Policy;

namespace Ghosts.Client.Handlers
{

    /// <summary>
    /// Supports upload, download, deletion of documents
    /// download, deletion only done from the first page
    /// </summary>
    public class SharepointHelper2013 : SharepointHelper
    {

        public SharepointHelper2013(BaseBrowserHandler callingHandler, IWebDriver callingDriver)
        {
            base.Init(callingHandler, callingDriver);

        }

        public override bool DoInitialLogin(TimelineHandler handler, string user, string pw)
        {
            //have the username, password
            RequestConfiguration config;

            string portal = site;

            string target = header + user + ":" + pw + "@" + portal + "/";
            config = RequestConfiguration.Load(handler, target);
            try
            {
                baseHandler.MakeRequest(config);
            }
            catch (System.Exception e)
            {
                Log.Trace($"Sharepoint:: Unable to parse site {site}, url may be malformed. Sharepoint browser action will not be executed.");
                baseHandler.sharepointAbort = true;
                Log.Error(e);
                return false;

            }
            target = header + portal + "/Documents/Forms/Allitems.aspx";
            config = RequestConfiguration.Load(handler, target);
            baseHandler.MakeRequest(config);
            //click on the files tab
            try
            {
                var targetElement = Driver.FindElement(By.Id("Ribbon.Document-title"));
                targetElement.Click();
            }
            catch (System.Exception e)
            {
                Log.Trace($"Sharepoint:: Unable to find Sharepoint menu, login may have failed, check the credentials. Sharepoint browser action will not be executed.");
                baseHandler.sharepointAbort = true;
                Log.Error(e);
                return false;

            }

            return true;
        }

        public override bool DoDownload(TimelineHandler handler)
        {

            Actions actions;

            try
            {
                var targetElements = Driver.FindElements(By.CssSelector("td[class='ms-cellStyleNonEditable ms-vb-itmcbx ms-vb-imgFirstCell']"));
                if (targetElements.Count > 0)
                {


                    int docNum = _random.Next(0, targetElements.Count);
                    var targetElement = targetElements[docNum];
                    MoveToElementAndClick(targetElement);
                    var checkboxElement = targetElement.FindElement(By.XPath(".//div[@role='checkbox']"));
                    string fname = checkboxElement.GetAttribute("title");

                    Thread.Sleep(1000);
                    //download it
                    targetElement = Driver.FindElement(By.Id("Ribbon.Documents.Copies.Download-Large"));
                    actions = new Actions(Driver);
                    actions.MoveToElement(targetElement).Click().Perform();

                    Thread.Sleep(1000);
                    //have to click on document element again to deselect it in order to enable next download
                    //targetElements[docNum].Click();  //select the doc
                    targetElement = targetElements[docNum];
                    MoveToElementAndClick(targetElement);
                    Log.Trace($"Sharepoint:: Downloaded file {fname} from site {site}.");
                    Thread.Sleep(1000);
                }
            }
            catch (Exception e)
            {
                Log.Trace($"Sharepoint:: Error performing sharepoint download from site {site}.");
                Log.Error(e);
            }
            return true;
        }

        /// <summary>
        /// If a sharepoint file upload is not accepted, deal with the error popup
        /// </summary>
        public bool UploadBlocked()
        {
            Actions actions;
            try
            {

                Driver.SwitchTo().ParentFrame();
                var targetElement = Driver.FindElement(By.XPath("//a[@class='ms-dlgCloseBtn']"));
                actions = new Actions(Driver);
                //close popup
                actions.MoveToElement(targetElement).Click().Perform();
                return true;  //was blocked
            }
            catch  //ignore any errors, upload may have not been blocked
            {

            }
            return false; //not blocked

        }

        public override bool DoUpload(TimelineHandler handler)
        {
            Actions actions;

            try
            {
                string fname = GetUploadFile();
                if (fname == null)
                {
                    Log.Trace($"Sharepoint:: Cannot find a valid file to upload from directory {uploadDirectory}.");
                    return true;
                }
                var span = new TimeSpan(0, 0, 0, 5, 0);
                var targetElement = Driver.FindElement(By.Id("Ribbon.Documents.New.AddDocument-Large"));
                actions = new Actions(Driver);
                actions.MoveToElement(targetElement).Click().Perform();
                Thread.Sleep(1000);
                Driver.SwitchTo().Frame(Driver.FindElement(By.ClassName("ms-dlgFrame")));
                WebDriverWait wait = new WebDriverWait(Driver, span);
                var uploadElement = Driver.FindElement(By.Id("ctl00_PlaceHolderMain_UploadDocumentSection_ctl05_InputFile"));
                uploadElement.SendKeys(fname);
                Thread.Sleep(500);
                var okElement = Driver.FindElement(By.Id("ctl00_PlaceHolderMain_ctl03_RptControls_btnOK"));
                actions = new Actions(Driver);
                actions.MoveToElement(okElement).Click().Perform();
                Thread.Sleep(500);
                if (UploadBlocked())
                {
                    Log.Trace($"Sharepoint:: Failed to upload file {fname} to site {site}.");
                }
                else
                {
                    Log.Trace($"Sharepoint:: Uploaded file {fname} to site {site}.");
                }


            }
            catch (Exception e)
            {
                Log.Trace($"Sharepoint:: Error performing sharepoint upload to site {site}.");
                Log.Error(e);
            }
            return true;
        }

        public override bool DoDelete(TimelineHandler handler)
        {
            Actions actions;
            //select a file to delete
            try
            {
                var targetElements = Driver.FindElements(By.CssSelector("td[class='ms-cellStyleNonEditable ms-vb-itmcbx ms-vb-imgFirstCell']"));
                if (targetElements.Count > 0)
                {
                    int docNum = _random.Next(0, targetElements.Count);
                    var targetElement = targetElements[docNum];
                    MoveToElementAndClick(targetElement);
                   
                    var checkboxElement = targetElements[docNum].FindElement(By.XPath(".//div[@role='checkbox']"));
                    string fname = checkboxElement.GetAttribute("title");

                    Thread.Sleep(1000);
                    //delete it
                    //somewhat weird, had to locate this element by the tooltip
                    targetElement = Driver.FindElement(By.CssSelector("a[aria-describedby='Ribbon.Documents.Manage.Delete_ToolTip'"));
                    actions = new Actions(Driver);
                    //deal with the popup
                    actions.MoveToElement(targetElement).Click().Perform();
                    Thread.Sleep(1000);
                    Driver.SwitchTo().Alert().Accept();
                    Log.Trace($"Sharepoint:: Deleted file {fname} from site {site}.");
                    Thread.Sleep(1000);
                }
                else
                {
                    Log.Trace($"Sharepoint:: No documents to delete from {site}.");
                }
            }
            catch (Exception e)
            {
                Log.Trace($"Sharepoint:: Error performing sharepoint download from site {site}.");
                Log.Error(e);
            }
            return true;
        }



    }

    /// <summary>
    /// Handles Sharepoint actions for base browser handler
    /// </summary>
    public abstract class SharepointHelper : BrowserHelper
    {

        
        private int _deletionProbability = -1;
        private int _uploadProbability = -1;
        private int _downloadProbability = -1;
        private Credentials _credentials = null;
        private string _state = "initial";
        public string site { get; set; } = null;
        string username { get; set; } = null;
        string password { get; set; } = null;
        public string header { get; set; } = null;

        string _version = null;
        public string uploadDirectory { get; set; } = null;

        

        public static SharepointHelper MakeHelper(BaseBrowserHandler callingHandler, IWebDriver callingDriver, TimelineHandler handler, Logger tlog)
        {
            SharepointHelper helper = null;
            if (handler.HandlerArgs.ContainsKey("sharepoint-version"))
            {
                var version = handler.HandlerArgs["sharepoint-version"].ToString();
                //this needs to be extended in the future
                if (version == "2013") helper = new SharepointHelper2013(callingHandler, callingDriver);

                if (helper == null)
                {
                    tlog.Trace($"Sharepoint:: Unsupported Sharepoint version {version} , sharepoint browser action will not be executed.");
                }
            }
            else
            {
                Log.Trace($"Sharepoint:: Handler option 'sharepoint-version' must be specified, currently supported versions: '2013'. Sharepoint browser action will not be executed.");

            }
            return helper;
        }

        

        public void Init(BaseBrowserHandler callingHandler, IWebDriver currentDriver)
        {
            baseHandler = callingHandler;
            Driver = currentDriver;
        }

        private bool CheckProbabilityVar(string name, int value)
        {
            if (!(value >= 0 && value <= 100))
            {
                Log.Trace($"Variable {name} with value {value} must be an int between 0 and 100, setting to 0");
                return false;
            }
            return true;
        }


        public string GetUploadFile()
        {
            try
            {
                string[] filelist = Directory.GetFiles(uploadDirectory, "*");
                if (filelist.Length > 0) return filelist[_random.Next(0, filelist.Length)];
                else return null;
            }
            catch { } //ignore any errors
            return null;
        }


        public virtual bool DoInitialLogin(TimelineHandler handler, string user, string pw)
        {
            Log.Trace($"Blog:: Unsupported action 'DoInitialLogin' in Blog version {_version} ");
            return false;
        }

        public virtual bool DoDownload(TimelineHandler handler)
        {
            Log.Trace($"Blog:: Unsupported action 'Browse' in Blog version {_version} ");
            return false;
        }

        public virtual bool DoDelete(TimelineHandler handler)
        {
            Log.Trace($"Blog:: Unsupported action 'Delete' in Blog version {_version} ");
            return false;
        }

        public virtual bool DoUpload(TimelineHandler handler)
        {
            Log.Trace($"Blog:: Unsupported action 'upload' in Blog version {_version} ");
            return true;
        }

        private string GetNextAction()
        {
            int choice = _random.Next(0, 101);
            string spAction = null;
            int endRange;
            int startRange = 0;

            if (_deletionProbability > 0)
            {
                endRange = _deletionProbability;
                if (choice >= startRange && choice <= endRange) spAction = "delete";
                else startRange = endRange + 1;
            }

            if (spAction == null && _uploadProbability > 0)
            {
                endRange = startRange + _uploadProbability;
                if (choice >= startRange && choice <= endRange) spAction = "upload";
                else startRange = endRange + 1;
            }

            if (spAction == null && _downloadProbability > 0)
            {
                endRange = startRange + _downloadProbability;
                if (choice >= startRange && choice <= endRange) spAction = "download";
                else startRange = endRange + 1;

            }

            return spAction;

        }

        /// <summary>
        /// This supports only one sharepoint site because it remembers context between runs. Different handlers should be used for different sites
        /// On the first execution, login is done to the site, then successive runs keep the login.
        /// </summary>
        /// <param name="handler"></param>
        /// <param name="timelineEvent"></param>
        public void Execute(TimelineHandler handler, TimelineEvent timelineEvent)
        {
            string credFname;
            string credentialKey = null;


            switch (_state)
            {


                case "initial":
                    //these are only parsed once, global for the handler as handler can only have one entry.
                    _version = handler.HandlerArgs["sharepoint-version"].ToString();  //guaranteed to have this option, parsed in calling handler


                    if (handler.HandlerArgs.ContainsKey("sharepoint-upload-directory"))
                    {
                        string targetDir = handler.HandlerArgs["sharepoint-upload-directory"].ToString();
                        targetDir = Environment.ExpandEnvironmentVariables(targetDir);
                        if (!Directory.Exists(targetDir))
                        {
                            Log.Trace($"Sharepoint:: upload directory {targetDir} does not exist, using browser downloads directory.");
                        }
                        else
                        {
                            uploadDirectory = targetDir;
                        }
                    }

                    if (uploadDirectory == null)
                    {
                        uploadDirectory = KnownFolders.GetDownloadFolderPath();
                    }


                    if (_deletionProbability < 0 && handler.HandlerArgs.ContainsKey("sharepoint-deletion-probability"))
                    {
                        int.TryParse(handler.HandlerArgs["sharepoint-deletion-probability"].ToString(), out _deletionProbability);
                        if (!CheckProbabilityVar(handler.HandlerArgs["sharepoint-deletion-probability"].ToString(), _deletionProbability))
                        {
                            _deletionProbability = 0;
                        }
                    }
                    if (_uploadProbability < 0 && handler.HandlerArgs.ContainsKey("sharepoint-upload-probability"))
                    {
                        int.TryParse(handler.HandlerArgs["sharepoint-upload-probability"].ToString(), out _uploadProbability);
                        if (!CheckProbabilityVar(handler.HandlerArgs["sharepoint-upload-probability"].ToString(), _uploadProbability))
                        {
                            _uploadProbability = 0;
                        }
                    }
                    if (_downloadProbability < 0 && handler.HandlerArgs.ContainsKey("sharepoint-download-probability"))
                    {
                        int.TryParse(handler.HandlerArgs["sharepoint-download-probability"].ToString(), out (_downloadProbability));
                        if (!CheckProbabilityVar(handler.HandlerArgs["sharepoint-download-probability"].ToString(), _downloadProbability))
                        {
                            _downloadProbability = 0;
                        }
                    }

                    if ((_deletionProbability + _uploadProbability + _downloadProbability) > 100)
                    {
                        Log.Trace($"Sharepoint:: The sum of the download/upload/deletion sharepoint probabilities is > 100 , sharepoint browser action will not be executed.");
                        baseHandler.sharepointAbort = true;
                        return;
                    }

                    if ((_deletionProbability + _uploadProbability + _downloadProbability) == 0)
                    {
                        Log.Trace($"Sharepoint:: The sum of the download/upload/deletion sharepoint probabilities == 0 , sharepoint browser action will not be executed.");
                        baseHandler.sharepointAbort = true;
                        return;
                    }

                    credFname = handler.HandlerArgs["sharepoint-credentials-file"].ToString();

                    if (handler.HandlerArgs.ContainsKey("sharepoint-credentials-file"))
                    {

                        try
                        {
                            _credentials = JsonConvert.DeserializeObject<Credentials>(System.IO.File.ReadAllText(credFname));
                        }
                        catch (System.Exception e)
                        {
                            Log.Trace($"Sharepoint:: Error parsing sharepoint credentials file {credFname} , sharepoint browser action will not be executed.");
                            baseHandler.sharepointAbort = true;
                            Log.Error(e);
                            return;
                        }
                    }

                    //now parse the command args
                    //parse the command args


                    char[] charSeparators = new char[] { ':' };
                    foreach (var cmd in timelineEvent.CommandArgs)
                    {
                        //each argument string is key:value, parse this
                        var argString = cmd.ToString();
                        if (!string.IsNullOrEmpty(argString))
                        {
                            var words = argString.Split(charSeparators, 2, StringSplitOptions.None);
                            if (words.Length == 2)
                            {
                                if (words[0] == "site") site = words[1];
                                else if (words[0] == "credentialKey") credentialKey = words[1];
                            }
                        }
                    }

                    if (site == null)
                    {
                        Log.Trace($"Sharepoint:: The command args must specify a 'site:<value>' , sharepoint browser action will not be executed.");
                        baseHandler.sharepointAbort = true;
                        return;
                    }

                    //check if site starts with http:// or https:// 
                    site = site.ToLower();
                    header = null;
                    Regex rx = new Regex("^http://.*", RegexOptions.Compiled);
                    var match = rx.Matches(site);
                    if (match.Count > 0) header = "http://";
                    if (header == null)
                    {
                        rx = new Regex("^https://.*", RegexOptions.Compiled);
                        match = rx.Matches(site);
                        if (match.Count > 0) header = "https://";
                    }
                    if (header != null)
                    {
                        site = site.Replace(header, "");
                    }
                    else
                    {
                        header = "http://";  //default header
                    }




                    if (credentialKey == null)
                    {
                        Log.Trace($"Sharepoint:: The command args must specify a 'credentialKey:<value>' , sharepoint browser action will not be executed.");
                        baseHandler.sharepointAbort = true;
                        return;
                    }

                    username = _credentials.GetUsername(credentialKey);
                    password = _credentials.GetPassword(credentialKey);

                    if (username == null || password == null)
                    {
                        Log.Trace($"Sharepoint:: The credential key {credentialKey} does not return a valid credential from file {credFname},   sharepoint browser action will not be executed");
                        baseHandler.sharepointAbort = true;
                        return;
                    }

                    //have username, password - do the initial login
                    if (!DoInitialLogin(handler, username, password))
                    {
                        baseHandler.blogAbort = true;
                        return;
                    }



                    //at this point we are logged in, files tab selected, ready for action
                    _state = "execute";
                    break;

                case "execute":

                    //determine what to do

                    string sharepointAction = GetNextAction();


                    if (sharepointAction == "download")
                    {
                        if (!DoDownload(handler))
                        {
                            baseHandler.blogAbort = true;
                            return;
                        }

                    }
                    if (sharepointAction == "upload")
                    {
                        if (!DoUpload(handler))
                        {
                            baseHandler.blogAbort = true;
                            return;
                        }
                    }

                    if (sharepointAction == "delete")
                    {
                        if (!DoDelete(handler))
                        {
                            baseHandler.blogAbort = true;
                            return;
                        }
                    }
                    break;


            }

        }


    }

    public abstract class BrowserHelper
    {
        public static readonly Logger Log = LogManager.GetCurrentClassLogger();
        internal static readonly Random _random = new Random();
        public BaseBrowserHandler baseHandler = null;
        public IWebDriver Driver = null;


        /// <summary>
        /// This is used when the element being moved to may be out of the viewport (ie, at the bottom of the page).
        /// Chrome handles this OK, but Firefox throws an exception, have to manually
        /// scroll to ensure the element is in view
        /// </summary>
        /// <param name="targetElement"></param>
        public void MoveToElementAndClick(IWebElement targetElement)
        {
            Actions actions;

            if (Driver is OpenQA.Selenium.Firefox.FirefoxDriver)
            {
                IJavaScriptExecutor je = (IJavaScriptExecutor)Driver;
                //be safe and scroll to element
                je.ExecuteScript("arguments[0].scrollIntoView()", targetElement);
                Thread.Sleep(500);
            }
            actions = new Actions(Driver);
            actions.MoveToElement(targetElement).Click().Perform();
        }

    }

}