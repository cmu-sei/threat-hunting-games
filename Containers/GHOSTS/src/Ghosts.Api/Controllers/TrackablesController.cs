using System;
using System.Threading;
using System.Threading.Tasks;
using Ghosts.Api.Services;
using Microsoft.AspNetCore.Mvc;

namespace ghosts.api.Controllers
{
    [Produces("application/json")]
    [Route("api/[controller]")]
    [ResponseCache(Duration = 5)]
    public class TrackablesController : Controller
    {
        private readonly ITrackableService _service;
        
        public TrackablesController(ITrackableService service)
        {
            _service = service;
        }
        
        /// <summary>
        /// Gets all trackables in the system
        /// </summary>
        /// <param name="ct">Cancellation Token</param>
        /// <returns>List of Trackables</returns>
        [HttpGet]
        public async Task<IActionResult> GetTrackables(CancellationToken ct)
        {
            var list = await _service.GetAsync(ct);
            if (list == null) return NotFound();
            return Ok(list);
        }
        
        [HttpGet("{id}")]
        public async Task<IActionResult> GetTrackableHistory([FromRoute] Guid id, CancellationToken ct)
        {
            var list = await _service.GetActivityByTrackableId(id, ct);
            if (list == null) return NotFound();
            return Ok(list);
        }
    }
}