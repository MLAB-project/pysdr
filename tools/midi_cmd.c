#include <jack/jack.h>
#include <jack/midiport.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

jack_client_t *client;
jack_port_t *port;

char message_outgoing;
char message[100];

int process(jack_nframes_t nframes, void *arg)
{
	void* port_buff = jack_port_get_buffer(port, nframes);
	jack_midi_clear_buffer(port_buff);

	if (message_outgoing) {
		size_t msg_len = strlen(message);

		unsigned char* buffer = jack_midi_event_reserve(port_buff, 0, msg_len + 3);
		buffer[0] = 0xf0;
		buffer[1] = 0x7d;
		memcpy(buffer + 2, message, msg_len);
		buffer[msg_len + 2] = 0xf7;

		message_outgoing = 0;
	}

	return 0;
}

int main(int narg, char **args)
{
	if ((client = jack_client_new("midi_cmd") == 0) {
		fprintf(stderr, "jack server not running?\n");
		return 1;
	}

	jack_set_process_callback(client, process, 0);
	port = jack_port_register(client, "out", JACK_DEFAULT_MIDI_TYPE, JackPortIsOutput, 0);
	message_outgoing = 0;

	if (jack_activate(client)) {
		fprintf(stderr, "cannot activate client");
		return 1;
	}

	while (1) {
		printf("(MIDI) ");
		fgets(message, sizeof(message), stdin);

		message[strlen(message) - 1] = '\0';
		message_outgoing = 1;
		while (message_outgoing);
	}
}
