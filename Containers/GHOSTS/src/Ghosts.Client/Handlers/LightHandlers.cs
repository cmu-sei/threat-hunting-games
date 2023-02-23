﻿// Copyright 2017 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using Ghosts.Client.Infrastructure;
using Ghosts.Domain;
using System;
using System.IO;
using System.Threading;

namespace Ghosts.Client.Handlers
{
    public class LightHandlers : BaseHandler
    {
        private static string GetSavePath(Type cls, TimelineHandler handler, TimelineEvent timelineEvent, string fileExtension)
        {
            Log.Trace($"{cls} event - {timelineEvent}");
            Infrastructure.WorkingHours.Is(handler);

            if (timelineEvent.DelayBefore > 0)
            {
                Thread.Sleep(timelineEvent.DelayBefore);
            }

            Thread.Sleep(3000);

            var rand = RandomFilename.Generate();

            var dir = timelineEvent.CommandArgs[0].ToString();
            if (dir.Contains("%"))
            {
                dir = Environment.ExpandEnvironmentVariables(dir);
            }

            if (Directory.Exists(dir))
            {
                Directory.CreateDirectory(dir);
            }

            var path = $"{dir}\\{rand}.{fileExtension}";

            //if directory does not exist, create!
            Log.Trace($"Checking directory at {path}");
            var f = new FileInfo(path).Directory;
            if (f == null)
            {
                Log.Trace($"Directory does not exist, creating directory at {path}");
                Directory.CreateDirectory(path);
            }

            try
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
            catch (Exception e)
            {
                Log.Debug(e);
            }

            Log.Trace($"{cls} saving to path - {path}");
            return path;
        }

        public class LightWordHandler : BaseHandler
        {
            public LightWordHandler(TimelineHandler handler)
            {
                base.Init(handler);
                Log.Trace("Launching Light Word handler");
                try
                {
                    if (handler.Loop)
                    {
                        Log.Trace("Light Word loop");
                        while (true)
                        {
                            ExecuteEvents(handler);
                        }
                    }
                    else
                    {
                        Log.Trace("Light Word single run");
                        ExecuteEvents(handler);
                    }
                }
                catch (Exception e)
                {
                    Log.Error(e);
                }
            }

            private void ExecuteEvents(TimelineHandler handler)
            {
                try
                {
                    foreach (var timelineEvent in handler.TimeLineEvents)
                    {
                        var path = GetSavePath(typeof(LightExcelHandler), handler, timelineEvent, "docx");

                        var list = RandomText.GetDictionary.GetDictionaryList();
                        using (var rt = new RandomText(list))
                        {
                            rt.AddSentence(5);

                            var title = rt.Content;
                            rt.AddContentParagraphs(2, 3, 5, 7, 22);
                            var paragraph = rt.Content;
                            Domain.Code.Office.Word.Write(path, title, paragraph);
                        }
                        
                        FileListing.Add(path, handler.HandlerType);
                        Report(handler.HandlerType.ToString(), timelineEvent.Command,
                            timelineEvent.CommandArgs[0].ToString());
                    }
                }
                catch (Exception e)
                {
                    Log.Error(e);
                }
            }
        }

        public class LightPowerPointHandler : BaseHandler
        {
            // TODO
        }

        public class LightExcelHandler : BaseHandler
        {
            public LightExcelHandler(TimelineHandler handler)
            {
                base.Init(handler);
                Log.Trace("Launching Light Excel handler");
                try
                {
                    if (handler.Loop)
                    {
                        Log.Trace("Light Excel loop");
                        while (true)
                        {
                            ExecuteEvents(handler);
                        }
                    }
                    else
                    {
                        Log.Trace("Light Excel single run");
                        ExecuteEvents(handler);
                    }
                }
                catch (Exception e)
                {
                    Log.Error(e);
                }
            }

            private void ExecuteEvents(TimelineHandler handler)
            {
                try
                {
                    foreach (var timelineEvent in handler.TimeLineEvents)
                    {
                        var path = GetSavePath(typeof(LightExcelHandler), handler, timelineEvent, "xlsx");

                        var list = RandomText.GetDictionary.GetDictionaryList();
                        using (var rt = new RandomText(list))
                        {
                            rt.AddSentence(5);
                            Domain.Code.Office.Excel.Write(path, rt.Content);
                        }

                        FileListing.Add(path, handler.HandlerType);
                        Report(handler.HandlerType.ToString(), timelineEvent.Command,
                            timelineEvent.CommandArgs[0].ToString());
                    }
                }
                catch (Exception e)
                {
                    Log.Error(e);
                }
            }
        }
    }
}