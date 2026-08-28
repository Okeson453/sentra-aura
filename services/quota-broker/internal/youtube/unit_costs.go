package youtube

import "sync"

// UnitCosts maps YouTube Data API operation names to quota unit costs.
// Costs are based on the official YouTube Data API quota documentation.
var defaultUnitCosts = map[string]int64{
	"videos.list":         1,
	"videos.insert":       1600,
	"videos.update":       50,
	"videos.delete":       50,
	"videos.rate":         50,
	"videos.getRating":    1,
	"channels.list":       1,
	"channels.update":     50,
	"playlists.list":      1,
	"playlists.insert":    50,
	"playlists.update":    50,
	"playlists.delete":    50,
	"playlistItems.list":  1,
	"playlistItems.insert": 50,
	"playlistItems.update": 50,
	"playlistItems.delete": 50,
	"search.list":         100,
	"subscriptions.list":  1,
	"subscriptions.insert": 50,
	"subscriptions.delete": 50,
	"commentThreads.list": 1,
	"commentThreads.insert": 50,
	"comments.list":       1,
	"comments.insert":     50,
	"comments.update":     50,
	"comments.delete":     50,
	"captions.list":       50,
	"captions.insert":     400,
	"captions.update":     450,
	"captions.delete":     50,
	"captions.download":   200,
	"channelSections.list": 1,
	"channelSections.insert": 50,
	"channelSections.update": 50,
	"channelSections.delete": 50,
	"i18nRegions.list":    1,
	"i18nLanguages.list":  1,
	"videoCategories.list": 1,
	"guideCategories.list": 1,
	"activities.list":     1,
}

var (
	unitCostMu   sync.RWMutex
	unitCostMap  = make(map[string]int64)
)

func init() {
	for k, v := range defaultUnitCosts {
		unitCostMap[k] = v
	}
}

// GetUnitCost returns the quota cost for an operation.
func GetUnitCost(operation string) int64 {
	unitCostMu.RLock()
	defer unitCostMu.RUnlock()
	if cost, ok := unitCostMap[operation]; ok {
		return cost
	}
	return 1 // Default fallback
}

// SetUnitCost overrides the cost for an operation (used for testing or API changes).
func SetUnitCost(operation string, cost int64) {
	unitCostMu.Lock()
	defer unitCostMu.Unlock()
	unitCostMap[operation] = cost
}
