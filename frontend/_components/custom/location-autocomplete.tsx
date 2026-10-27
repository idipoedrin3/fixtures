"use client";

import {useState, useEffect, useRef} from "react";
import {Check, ChevronsUpDown, MapPin} from "lucide-react";

import {cn} from "@/lib/utils";
import {Button} from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Spinner} from "@/components/ui/spinner";
import {ScrollArea} from "@/components/ui/scroll-area";
import {toast} from "@/components/ui/use-toast";
import {GEOLOCATION_API} from "#/_api/helpers";

interface LocationOption {
  value: string;
  label: string;
  address: string;
}

interface LocationAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  showCurrentLocationButton?: boolean;
  onCoordinatesChange?: (lat: string, lon: string) => void;
}

export function LocationAutocomplete({
  value,
  onChange,
  onCoordinatesChange,
  placeholder = "Search for a location...",
  className,
  showCurrentLocationButton = true,
}: LocationAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value);
  const [options, setOptions] = useState<LocationOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [gettingCurrentLocation, setGettingCurrentLocation] = useState(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Update input value when external value changes
    setInputValue(value);
  }, [value]);

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const fetchLocations = async (query: string) => {
    if (!query || query.length < 2) {
      setOptions([]);

      return;
    }

    setLoading(true);
    try {
      const response = await GEOLOCATION_API.autocomplete({query});

      if (!response.ok) {
        throw new Error("Failed to fetch locations");
      }

      const data = await response.json();

      if (data.features && data.features.length > 0) {
        const locationOptions = data.features.map((feature: any) => {
          const properties = feature.properties;
          const formattedAddress = properties.formatted;

          return {
            value: formattedAddress,
            label: properties.name || properties.street || formattedAddress.split(",")[0],
            address: formattedAddress,
          };
        });

        setOptions(locationOptions);
      } else {
        setOptions([]);
      }
    } catch (error) {
      // console.error("Error fetching location suggestions:", error);
      setOptions([]);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (value: string) => {
    setInputValue(value);

    // Debounce API calls
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      fetchLocations(value);
    }, 300);
  };

  const handleSelectLocation = async (location: string) => {
    onChange(location);
    setInputValue(location);
    setOpen(false);

    try {
      const response = await GEOLOCATION_API.search({location});

      if (!response.ok) throw new Error("Failed to get coordinates");

      const data = await response.json();

      if (data.features && data.features.length > 0) {
        const coords = data.features[0].geometry.coordinates;
        const [lon, lat] = coords;

        onCoordinatesChange?.(lat.toString(), lon.toString());
      }
    } catch (error) {
      // console.error("Failed to get coordinates from selected location:", error);
    }
  };

  const handleUseCustomLocation = () => {
    const customLocation = inputValue.trim();

    if (!customLocation) return;

    onChange(customLocation);
    onCoordinatesChange?.("", "");
    setInputValue(customLocation);
    setOpen(false);
  };

  const getCurrentLocation = () => {
    if (!navigator.geolocation) {
      toast({
        title: "Geolocation not supported",
        description: "Your browser does not support geolocation.",
        variant: "destructive",
      });

      return;
    }

    setGettingCurrentLocation(true);

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const {latitude, longitude} = position.coords;

          // Use Geoapify reverse geocoding API
          const response = await GEOLOCATION_API.reverse({latitude, longitude});

          if (!response.ok) {
            throw new Error("Failed to reverse geocode location");
          }

          const data = await response.json();

          if (data.features && data.features.length > 0) {
            const address = data.features[0].properties.formatted;

            handleSelectLocation(address);
            toast({
              title: "Location found",
              description: "Your current location has been set.",
            });
          } else {
            throw new Error("No address found for your location");
          }
        } catch (error) {
          // console.error("Error getting current location:", error);
          toast({
            title: "Error getting location",
            description:
              error instanceof Error ? error.message : "Failed to get your current location",
            variant: "destructive",
          });
        } finally {
          setGettingCurrentLocation(false);
        }
      },
      (error) => {
        // console.error("Geolocation error:", error);
        let errorMessage = "Failed to get your location";

        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage = "Location permission denied. Please enable location services.";
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage = "Location information is unavailable.";
            break;
          case error.TIMEOUT:
            errorMessage = "Location request timed out.";
            break;
        }

        toast({
          title: "Location error",
          description: errorMessage,
          variant: "destructive",
        });
        setGettingCurrentLocation(false);
      },
      {enableHighAccuracy: true, timeout: 10000, maximumAge: 0},
    );
  };

  return (
    <div className="w-full">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            aria-expanded={open}
            className={cn("w-full justify-between text-left", className)}
            role="combobox"
            title={value} // Add title attribute for tooltip on hover
            variant="outline"
          >
            {value ? (
              <div className="flex items-center w-full">
                <MapPin className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="truncate">{value}</span>
              </div>
            ) : (
              <span className="text-muted-foreground">{placeholder}</span>
            )}
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[350px] p-0 z-[1100]" side="bottom">
          <Command shouldFilter={false}>
            <CommandInput
              className="border-none"
              placeholder={placeholder}
              value={inputValue}
              onValueChange={handleInputChange}
            />
            <CommandList>
              {loading ? (
                <div className="flex items-center justify-center py-6">
                  <Spinner className="h-4 w-4 mr-2" />
                  <span className="text-sm text-muted-foreground">Searching locations...</span>
                </div>
              ) : inputValue.length > 0 ? (
                <CommandEmpty>
                  <div className="py-6 text-center">
                    <p className="text-sm text-muted-foreground">No suggested locations found</p>
                  </div>
                </CommandEmpty>
              ) : (
                <CommandEmpty>
                  <div className="py-6 text-center">
                    <p className="text-sm text-muted-foreground">Type to search for locations</p>
                  </div>
                </CommandEmpty>
              )}
              <CommandGroup>
                <ScrollArea className="max-h-[300px]">
                  {inputValue.trim() && (
                    <CommandItem
                      className="flex items-start gap-2 py-3"
                      value={`custom:${inputValue}`}
                      onSelect={handleUseCustomLocation}
                    >
                      <MapPin className="mt-1 h-4 w-4 shrink-0" />
                      <div className="flex flex-col overflow-hidden">
                        <span className="font-medium">Use this address</span>
                        <span className="text-xs text-muted-foreground break-words">
                          {inputValue.trim()}
                        </span>
                      </div>
                    </CommandItem>
                  )}
                  {options.map((option) => (
                    <CommandItem
                      key={option.value}
                      className="flex flex-col items-start py-3"
                      value={option.value}
                      onSelect={() => handleSelectLocation(option.value)}
                    >
                      <div className="flex items-start gap-2 w-full">
                        <Check
                          className={cn(
                            "mt-1 h-4 w-4 flex-shrink-0",
                            value === option.value ? "opacity-100" : "opacity-0",
                          )}
                        />
                        <div className="flex flex-col overflow-hidden w-full">
                          <span className="font-medium">{option.label}</span>
                          <span className="text-xs text-muted-foreground break-words">
                            {option.address}
                          </span>
                        </div>
                      </div>
                    </CommandItem>
                  ))}
                </ScrollArea>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
