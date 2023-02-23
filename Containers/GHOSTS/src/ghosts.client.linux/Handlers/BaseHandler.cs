﻿// Copyright 2017 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using System;
using Ghosts.Domain;
using Ghosts.Domain.Code;
using NLog;
using Newtonsoft.Json;

namespace ghosts.client.linux.handlers
{
    public abstract class BaseHandler
    {
        public static readonly Logger _log = LogManager.GetCurrentClassLogger();
        private static readonly Logger _timelineLog = LogManager.GetLogger("TIMELINE");
        internal static readonly Random _random = new Random();
        
        public void Init(TimelineHandler handler)
        {
            WorkingHours.Is(handler);
        }

        protected static void Report(string handler, string command, string arg, string trackable = null)
        {
            var result = new TimeLineRecord
            {
                Handler = handler,
                Command = command,
                CommandArg = arg
            };

            if (!string.IsNullOrEmpty(trackable))
            {
                result.TrackableId = trackable;
            }

            var o = JsonConvert.SerializeObject(result,
                Formatting.None,
                new JsonSerializerSettings
                {
                    NullValueHandling = NullValueHandling.Ignore
                });

            _timelineLog.Info($"TIMELINE|{DateTime.UtcNow}|{o}");
        }
    }
}